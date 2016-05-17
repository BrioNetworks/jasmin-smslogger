# -*- coding: utf-8 -*-
import time
from datetime import datetime, timedelta
from smslogger import settings

if settings.USE_JASMIN:
    from jasmin.vendor.enum import EnumValue
    from jasmin.vendor.smpp.pdu.pdu_types import DataCoding
else:
    from enum import EnumValue
    from smpp.pdu.pdu_types import DataCoding


def decode_message(short_message, dc):
    # UCS2 or UnicodeFlashSMS
    if (isinstance(dc, int) and dc == 8) \
            or (isinstance(dc, DataCoding) and str(dc.schemeData) == 'UCS2') \
            or (isinstance(dc.schemeData, EnumValue) and dc.schemeData.index == 0) \
            or dc.schemeData == 24:
        short_message = short_message.decode('utf_16_be', 'ignore')
    return short_message


def try_parsing_date(text):
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError('no valid date format found')


def utc_to_local(utc_time_str):
    hours = 3
    diff_hours = time.localtime()[hours] - time.gmtime()[hours]
    utc_time = try_parsing_date(utc_time_str)
    local_time = utc_time + timedelta(hours=diff_hours)
    return local_time


def get_multipart_message(pdu, short_message):
    pdu_count = 1
    if short_message:
        while hasattr(pdu, 'nextPdu'):
            # Remove UDH from first part
            if pdu_count == 1:
                short_message = short_message[6:]
            pdu = pdu.nextPdu
            # Update values:
            pdu_count += 1
            short_message += pdu.params['short_message'][6:]
    return pdu_count, short_message
