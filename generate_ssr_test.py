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


"""Tests for generate_ssr."""

import contextlib
import StringIO
import sys

import generate_ssr

import google.protobuf.text_format as text_format

SAMPLE_RESPONSE = {u'items': [
    {u'HTMLSnippet': u'<a href="http://www.test.com">Hi there!</a>',
     u'accountId': 123456789,
     u'advertiserId': [u'12345'],
     u'advertiserName': u'test',
     u'attribute': [generate_ssr.RICH_MEDIA_CAPABILITY_SSL],
     u'buyerCreativeId': u'buyer_creative_id_test',
     u'clickThroughUrl': [u'http://www.test.com/'],
     u'corrections': [{u'details': [u'test correction detail 1',
                                    u'test correction detail 2'],
                       u'reason': 'VENDOR_IDS'},
                      {u'details': [u'test correction detail 3',
                                    u'test correction detail 4'],
                       u'reason': 'FLASH_ATTRIBUTE'},
                     ],
     u'disapprovalReasons': [
         {u'details': [u'No click macro was declared in the snippet'],
          u'reason': u'PROBLEM_WITH_CLICK_MACRO'}],
     u'filteringReasons': {u'date': '1900-01-01',
                           u'reasons': [{'filteringCount': 200,
                                         'filteringStatus': 1},
                                        {'filteringCount': 100,
                                         'filteringStatus': 2}
                                       ]
                          },
     u'height': 250,
     u'kind': u'adexchangebuyer#creative',
     u'productCategories': [10004,
                            10019,
                            10108,
                            10168, 10756,
                            10885,
                            12204,
                            13094,
                            13418,
                            13432],
     u'status': u'DISAPPROVED',
     u'width': 300}]}

SAMPLE_RESPONSE_TRANSLATED= {u'items': [
    {u'HTMLSnippet': u'<a href="http://www.test.com">Hi there!</a>',
     u'accountId': 123456789,
     u'advertiser_id': [u'12345'],
     u'advertiserName': u'test',
     u'attribute': [generate_ssr.RICH_MEDIA_CAPABILITY_SSL],
     u'buyer_creative_id': u'buyer_creative_id_test',
     u'click_through_url': [u'http://www.test.com/'],
     u'snippet_correction': [
         {u'detail': [u'test correction detail 1',
                      u'test correction detail 2'],
          u'type': 'VENDOR_IDS'},
         {u'detail': [u'test correction detail 3',
                      u'test correction detail 4'],
          u'type': 'FLASH_ATTRIBUTE'},
         ],
     u'disapproval_reason': [
         {u'detail': [u'No click macro was declared in the snippet'],
          u'reason': u'PROBLEM_WITH_CLICK_MACRO'}],
     u'snippet_filtering': {u'date': '1900-01-01',
                            u'item': [{'filtering_count': 200,
                                       'filtering_status': 1},
                                      {'filtering_count': 100,
                                       'filtering_status': 2}
                                     ]
                           },
     u'height': 250,
     u'kind': u'adexchangebuyer#creative',
     u'detected_product_category': [10004,
                                    10019,
                                    10108,
                                    10168,
                                    10756,
                                    10885,
                                    12204,
                                    13094,
                                    13418,
                                    13432],
     u'status': u'DISAPPROVED',
     u'width': 300}]}

SSL_DECLARED = {
    u'buyerCreativeId': u'buyer_creative_id_test',
    u'attribute': [generate_ssr.RICH_MEDIA_CAPABILITY_SSL],
    u'snippet_correction': [
        {'detail': [u'flashess not declared but flash not detected'],
         u'type': generate_ssr.FLASHLESS_ATTRIBUTE}]}

SSL_NOT_DECLARED = {u'buyer_creative_id': u'buyer_creative_id_test'}

SSL_DECLARED_DISAPPROVED_FOR_SSL = {
    u'buyer_creative_id': u'buyer_creative_id_test',
    u'attribute': [generate_ssr.RICH_MEDIA_CAPABILITY_SSL],
    u'disapproval_reason': [
        {u'detail': [u'ssl declared but not supported'],
         u'reason': generate_ssr.INVALID_SSL_DECLARATION}]}

SSL_DECLARED_CORRECTED_FOR_SSL = {
    u'buyer_creative_id': u'buyer_creative_id_test',
    u'attribute': [generate_ssr.RICH_MEDIA_CAPABILITY_SSL],
    u'snippet_correction': [
        {u'detail': [u'ssl declared but not supported'],
         u'type': generate_ssr.SSL_ATTRIBUTE}]}

SSL_ATTRIBUTE_CORRECTION = {u'detail': [u'ssl declared but not supported'],
                            u'type': generate_ssr.SSL_ATTRIBUTE}

FLASHLESS_ATTRIBUTE_CORRECTION = {
    u'detail': [u'flashess not declared but flash not detected'],
    u'type': generate_ssr.FLASHLESS_ATTRIBUTE}

FLASHLESS_ATTRIBUTE_INCLUDED = {
    u'snippet_correction': [SSL_ATTRIBUTE_CORRECTION,
                            FLASHLESS_ATTRIBUTE_CORRECTION]}


def TestReplaceKey():
  d = {'old': 'foo'}
  generate_ssr._ReplaceKey(d, 'old', 'new')
  assert 'old' not in d
  assert d['new'] == 'foo'


def TestReplaceJSONFields():
  translated_response = SAMPLE_RESPONSE.copy()
  generate_ssr._ReplaceJSONFields(translated_response['items'][0],
                                  generate_ssr.KEY_TRANSLATION, '')
  assert translated_response == SAMPLE_RESPONSE_TRANSLATED


def TestRemoveFlashlessAttributeCorrection():
  generate_ssr._RemoveFlashlessAttributeCorrection(FLASHLESS_ATTRIBUTE_INCLUDED)
  assert (SSL_ATTRIBUTE_CORRECTION in
          FLASHLESS_ATTRIBUTE_INCLUDED['snippet_correction'])
  assert (FLASHLESS_ATTRIBUTE_CORRECTION not in
          FLASHLESS_ATTRIBUTE_INCLUDED['snippet_correction'])


def TestIsSSLCapable():
  assert generate_ssr._IsSSLCapable(SSL_DECLARED)
  assert not generate_ssr._IsSSLCapable(SSL_NOT_DECLARED)
  assert not generate_ssr._IsSSLCapable(SSL_DECLARED_DISAPPROVED_FOR_SSL)
  assert not generate_ssr._IsSSLCapable(SSL_DECLARED_CORRECTED_FOR_SSL)


def TestGenerateSnippetStatusReport():
  report = generate_ssr.GenerateSnippetStatusReportPBObject(SAMPLE_RESPONSE)

  with contextlib.closing(StringIO.StringIO()) as report_txt:
    text_format.PrintMessage(report, report_txt)
    with open('expected.txt', 'r') as expected_txt:
      assert report_txt.getvalue() == expected_txt.read()

  with contextlib.closing(StringIO.StringIO()) as report_pb:
    report_pb.write(report.SerializeToString())
    with open('expected.pb', 'r') as expected_pb:
      assert report_pb.getvalue() == expected_pb.read()

  with contextlib.closing(StringIO.StringIO()) as report_csv:
    generate_ssr.WriteSnippetStatusReportInCSV(report, report_csv)
    with open('expected.csv', 'r') as expected_csv:
      assert report_csv.getvalue() == expected_csv.read()


def main(_):
  TestReplaceKey()
  TestReplaceJSONFields()
  TestIsSSLCapable()
  TestRemoveFlashlessAttributeCorrection()
  TestGenerateSnippetStatusReport()
  print 'All Tests Passed'

if __name__ == '__main__':
  main(sys.argv)

