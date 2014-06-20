# Copyright 2014 Google Inc. All Rights Reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This program generates Snippet Status Reports.

The program calls the Google Ad-Exchange Buyer API, and generates
Snippet Status Reports in txt, pb, and csv format.

  Usage:

  python generate_ssr.py

Output files are SnippetStatusReport.txt, SnippetStatusReport.pb,
and SnippetStatusReport.csv
"""

import argparse
import contextlib
import csv
import StringIO
import sys

from apiclient import sample_tools
from oauth2client import client

from third_party.protobuf_json import protobuf_json
import snippet_status_report_pb2

import google.protobuf.descriptor as descriptor
import google.protobuf.text_format as text_format


RICH_MEDIA_CAPABILITY_SSL = 47
INVALID_SSL_DECLARATION = u'INVALID_SSL_DECLARATION'
SSL_ATTRIBUTE = u'SSL_ATTRIBUTE'
FLASHLESS_ATTRIBUTE = u'FLASHLESS_ATTRIBUTE'

KEY_TRANSLATION = {
    u'advertiserId': u'advertiser_id',
    u'buyerCreativeId': u'buyer_creative_id',
    u'clickThroughUrl': u'click_through_url',
    u'corrections': u'snippet_correction',
    u'corrections.details': u'detail',
    u'corrections.reason': u'type',
    u'disapprovalReasons': u'disapproval_reason',
    u'disapprovalReasons.details': u'detail',
    u'disapprovalReasons.reason': u'reason',
    u'filteringReasons': u'snippet_filtering',
    u'filteringReasons.date': u'date',
    u'filteringReasons.reasons': u'item',
    u'filteringReasons.reasons.filteringCount': u'filtering_count',
    u'filteringReasons.reasons.filteringStatus': u'filtering_status',
    u'height': u'height',
    u'productCategories': u'detected_product_category',
    u'sensitiveCategories': u'detected_sensitive_category',
    u'status': u'status',
    u'width': u'width'}

# Declare command-line flags.
argparser = argparse.ArgumentParser(add_help=False)


def _ReplaceKey(dictionary, old_key, new_key):
  if old_key in dictionary:
    dictionary[new_key] = dictionary.pop(old_key)


def _ReplaceJSONFields(json, translation, prefix):
  """Traverses JSON hierarchy, renaming keys indicated by translation table.

  Args:
    json: JSON data to modify.
    translation: Table of key translations for JSON.
    prefix: String representing current position in JSON hierarchy.
  """
  if type(json) is list:
    for item in json:
      _ReplaceJSONFields(item, translation, prefix)
  elif type(json) is dict:
    for field_name in json:
      full_key = prefix + field_name
      if full_key in translation:
        new_key = translation[full_key]
        _ReplaceKey(json, field_name, new_key)
        _ReplaceJSONFields(json[new_key], translation, full_key + '.')


def _RemoveFlashlessAttributeCorrection(item):
  """Remove FLASHLESS_ATTRIBUTE if it's one of the correction reasons.

  This correction reason is not exposed in the protobol buffer, and therefore
  it needs to be removed
  Args:
    item: snippet status item to process
  """
  for snippet_correction in item.get('snippet_correction', []):
    if snippet_correction.get('type', None) == FLASHLESS_ATTRIBUTE:
      item['snippet_correction'].remove(snippet_correction)


def _IsSSLCapable(item):
  """Checkes whether a Snippet Status Item is SSL Capable.

  Args:
    item: a dictionary that represents one Snippet Status Item
  Returns:
    True if 1. RICH_MEDIA_CAPABILITY_SSL is declared in the attribute
            2. The snippet is not disapproved for INVALID_SSL_DECLARATION
            3. The snippet is not corrected for SSL_ATTRIBUTE
    False otherwise
  """
  if RICH_MEDIA_CAPABILITY_SSL not in item.get('attribute', []):
    return False
  for disapproval_reason in item.get('disapproval_reason', []):
    if disapproval_reason.get('reason', None) == INVALID_SSL_DECLARATION:
      return False
  for snippet_correction in item.get('snippet_correction', []):
    if snippet_correction.get('type', None) == SSL_ATTRIBUTE:
      return False
  return True


def GenerateSnippetStatusReportPBObject(response):
  """Generates Snippet Status Reports as a Protocol Buffer object.

  Args:
    response: A dictionary containing response from the creative.list API
        call
  Returns:
    a Snippet Status Report Protocol Buffer Object
  """
  report = snippet_status_report_pb2.SnippetStatusReport()

  # Convert the report to a protocol buffer
  for item in response['items']:
    snippet_status = report.snippet_status.add()
    _ReplaceJSONFields(item, KEY_TRANSLATION, '')
    translated_item = item.copy()  # Make a copy so we can keep the original
    _RemoveFlashlessAttributeCorrection(item)
    protobuf_json.json2pb(snippet_status, translated_item, True)

    # Fill in fields that are not directly read from the response:
    snippet_status.source = snippet_status_report_pb2.SnippetStatusItem.RTB
    snippet_status.is_ssl_capable = _IsSSLCapable(translated_item)

  return report


def WriteSnippetStatusReportInCSV(report, report_csv):
  """Write the Snippet Status Report in csv format in the output stream.

  Args:
    report: Snippet Status Report as a protobol buffer object
    report_csv: output stream to write to
  """
  if not report_csv:
    return

  writer = csv.writer(report_csv)
  fields = snippet_status_report_pb2.SnippetStatusItem.DESCRIPTOR.fields
  active_fields = [field for field in fields
                   if not field.name.startswith('DEPRECATED_')]

  header_row = [field.name for field in active_fields]
  writer.writerow(header_row)

  def FieldSingletonAsString(field, value):
    """Generates string value for a field singleton."""
    with contextlib.closing(StringIO.StringIO()) as buf:
      text_format.PrintFieldValue(field, value, buf, as_one_line=True)
      return buf.getvalue()

  def FieldAsString(field, value):
    """Generates string value for a field.  Handles repeated fields."""
    if field.label == descriptor.FieldDescriptor.LABEL_REPEATED:
      items = [FieldSingletonAsString(field, item) for item in value]
      return '[%s]' % (';'.join(items))
    else:
      return FieldSingletonAsString(field, value)

  def SnippetStatusColumns(snippet_status):
    """Generates columns for a snippet status row."""
    for field in active_fields:
      yield FieldAsString(field, getattr(snippet_status, field.name, None))

  for snippet_status in report.snippet_status:
    columns = list(SnippetStatusColumns(snippet_status))
    writer.writerow(columns)


def main(argv):
  # Authenticate and construct service.
  service, _ = sample_tools.init(
      argv, 'adexchangebuyer', 'v1.3', __doc__, __file__, parents=[argparser],
      scope='https://www.googleapis.com/auth/adexchange.buyer')

  try:
    # Construct a list request.
    request = service.creatives().list()
    # Execute the request and store the response.
    response = request.execute()
  except client.AccessTokenRefreshError:
    print ('The credentials have been revoked or expired, please re-run the '
           'application to re-authorize')

  # Generate a Snippet Status Report Protocol buffer object
  report = GenerateSnippetStatusReportPBObject(response)

  # Write the report to files in txt, pb and csv format
  with open('SnippetStatusReport.txt', 'w') as report_txt:
    text_format.PrintMessage(report, report_txt)
  with open('SnippetStatusReport.pb', 'wb') as report_pb:
    report_pb.write(report.SerializeToString())
  with open('SnippetStatusReport.csv', 'w') as report_csv:
    WriteSnippetStatusReportInCSV(report, report_csv)

if __name__ == '__main__':
  main(sys.argv)
