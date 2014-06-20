# JSON serialization support for Google's protobuf Messages
# Copyright (c) 2009, Paul Dovbush
# All rights reserved.
# http://code.google.com/p/protobuf-json/
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of <ORGANIZATION> nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Provide serialization and de-serialization between protobufs and JSON format.

JSON here does not refer to the text format, but rather to the Python builtin
data types that correspond to the parts of a JSON document.

Namely: dict, list, str, int/float, bool and NoneType.
"""

# Note that preservation of unknown fields is currently not available for Python (c) google docs
# extensions is not supported from 0.0.5 (due to gpb2.3 changes)

__version__='0.0.5'
__author__='Paul Dovbush <dpp@dpp.su>'

import sys

from google.protobuf.descriptor import FieldDescriptor as FD


class ParseError(Exception): pass


class RequiredFieldMissing(Exception): pass


def _EnumNameToNumber(field):
  def _Ftype(js_value):
    value_desc = field.enum_type.values_by_name.get(js_value)
    return value_desc.number if value_desc else int(js_value)
  return _Ftype


def _EnumNumberToName(field):
  def _Ftype(js_value):
    value_desc = field.enum_type.values_by_number.get(js_value)
    return value_desc.name if value_desc else js_value
  return _Ftype


def json2pb(pb, js, use_enum_str_values=False):
  """Fills the protobuf `pb` with the corresponding values in the dict `js`.

  Args:
    pb: An empty protobuf object.
    js: A dictionary with keys corresponding to protobuf fields.
    use_enum_str_values: Boolean to convert enumeration strings into their
      integer values.

  Raises:
    RequiredFieldMissing: If a required field is missing.
    ParseError: If a field of an unknown type is encountered.

  Returns:
    pb populated with values.
  """
  try:
    module = sys.modules[pb.__module__]
  except KeyError:
    # Modules generated under third_party have their __module__ field
    # incorrectly qualified, so work around.
    without_third_party = pb.__module__.replace('google3.third_party.py.', '')
    module = sys.modules[without_third_party]

  for field in pb.DESCRIPTOR.fields:
    if field.name not in js:
      continue
    if field.type in [FD.TYPE_MESSAGE, FD.TYPE_GROUP]:
      pass
    elif use_enum_str_values and field.type == FD.TYPE_ENUM:
      ftype = _EnumNameToNumber(field)
    elif field.type in _js2ftype:
      ftype = _js2ftype[field.type]
    else:
      raise ParseError("Field %s.%s of type '%d' is not supported" % (
          pb.__class__.__name__, field.name, field.type, ))
    js_value = js[field.name]
    pb_value = getattr(pb, field.name)
    if field.label == FD.LABEL_REPEATED:
      for v in js_value:
        if _IsMessageSet(field):
          _MessageSetJson2Pb(module, pb_value.add(), v, use_enum_str_values)
        elif field.type in [FD.TYPE_MESSAGE, FD.TYPE_GROUP]:
          json2pb(pb_value.add(), v, use_enum_str_values=use_enum_str_values)
        else:
          pb_value.append(ftype(v))
    else:
      if _IsMessageSet(field):
        _MessageSetJson2Pb(module, pb_value, js_value, use_enum_str_values)
      elif field.type in [FD.TYPE_MESSAGE, FD.TYPE_GROUP]:
        json2pb(pb_value, js_value, use_enum_str_values=use_enum_str_values)
      else:
        setattr(pb, field.name, ftype(js_value))

  init_errors = pb.FindInitializationErrors()
  if init_errors:
    raise RequiredFieldMissing('Required fields %s missing' % str(init_errors))
  return pb


def _MessageSetPb2Json(message_set, use_enum_str_values, all_fields):
  js_value = {}
  # I don't know another way to iterate over the fields of the message set,
  # other than to use the protected _fields attribute.
  #pylint: disable-msg=W0212
  for field, value in message_set._fields.iteritems():
    contents = dict((k.name, _Pb2JsonConverter(k, use_enum_str_values,
                                               all_fields)(v))
                    for k, v in value._fields.iteritems())
    js_value[field.message_type.name] = contents
  return js_value


def _MessageSetJson2Pb(module, pb_msg, json_message_set, use_enum_str_values):
  for type_name, contents in json_message_set.iteritems():
    typ = getattr(module, type_name)
    message = pb_msg.Extensions[typ.message_set_extension]
    json2pb(message, contents, use_enum_str_values=use_enum_str_values)


def _IsMessageSet(field):
  return (field.type == FD.TYPE_MESSAGE and
          field.message_type.full_name == 'proto2.bridge.MessageSet')


def _Pb2JsonConverter(field, use_enum_str_values, all_fields):
  """Returns a function to convert a value of field's type into a json value."""
  if _IsMessageSet(field):
    # Lambda is used to preserve value of use_enum_str_values and all_fields
    return lambda x: _MessageSetPb2Json(x, use_enum_str_values, all_fields)
  elif use_enum_str_values and field.type == FD.TYPE_ENUM:
    return _EnumNumberToName(field)
  elif field.type in _ftype2js:
    ftype = _ftype2js[field.type]
    if ftype == pb2json:
      # Lambda is used to preserve values of use_enum_str_values and all_fields
      return lambda x: pb2json(x, use_enum_str_values=use_enum_str_values,
                               all_fields=all_fields)
    else:
      return ftype
  else:
    raise ParseError("Field %s of type '%d' is not supported" % (
        field.full_name, field.type))


def pb2json(pb, use_enum_str_values=False, all_fields=False):
  """Returns a dict with values corresponding to the fields in protobuf `pb`.

  Args:
    pb: A protobuf object
    use_enum_str_values: Boolean to renders enumeration values as strings
      instead of integers.
    all_fields: Renders all fields to JSON, even optional (as None) and
      empty repeated fields (as empty lists).

  Raises:
    RequiredFieldMissing: If a required field is missing.

  Returns:
    A dict form of pb.
  """
  js = {}

  if all_fields:
    field_values = ((f, getattr(pb, f.name)) for f in pb.DESCRIPTOR.fields)
  else:
    field_values = pb.ListFields()

  for field, value in field_values:
    if (all_fields and field.label == FD.LABEL_OPTIONAL and
        not pb.HasField(field.name)):
      js[field.name] = None
    else:
      ftype = _Pb2JsonConverter(field, use_enum_str_values, all_fields)
      if field.label == FD.LABEL_REPEATED:
        js_value = map(ftype, value)
      else:
        js_value = ftype(value)
      js[field.name] = js_value

  init_errors = pb.FindInitializationErrors()
  if init_errors:
    raise RequiredFieldMissing('Required fields %s missing' % str(init_errors))
  return js


_ftype2js = {
    FD.TYPE_DOUBLE: float,
    FD.TYPE_FLOAT: float,
    FD.TYPE_INT64: long,
    FD.TYPE_UINT64: long,
    FD.TYPE_INT32: int,
    FD.TYPE_FIXED32: int,
    FD.TYPE_FIXED64: long,
    FD.TYPE_BOOL: bool,
    FD.TYPE_STRING: unicode,
    FD.TYPE_GROUP: pb2json,
    FD.TYPE_MESSAGE: pb2json,
    FD.TYPE_BYTES: lambda x: x.encode('string_escape'),
    FD.TYPE_UINT32: int,
    FD.TYPE_ENUM: int,
    FD.TYPE_SFIXED32: int,
    FD.TYPE_SFIXED64: long,
    FD.TYPE_SINT32: int,
    FD.TYPE_SINT64: long,
    }

_js2ftype = {
    FD.TYPE_DOUBLE: float,
    FD.TYPE_FLOAT: float,
    FD.TYPE_INT64: long,
    FD.TYPE_UINT64: long,
    FD.TYPE_INT32: int,
    FD.TYPE_FIXED32: int,
    FD.TYPE_FIXED64: long,
    FD.TYPE_BOOL: bool,
    FD.TYPE_STRING: unicode,
    # FD.TYPE_MESSAGE: json2pb,  #handled specially
    FD.TYPE_BYTES: lambda x: x.decode('string_escape'),
    FD.TYPE_UINT32: int,
    FD.TYPE_ENUM: int,
    FD.TYPE_SFIXED32: int,
    FD.TYPE_SFIXED64: long,
    FD.TYPE_SINT32: int,
    FD.TYPE_SINT64: long,
    }
