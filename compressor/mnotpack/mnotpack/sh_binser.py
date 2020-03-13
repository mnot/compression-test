
"""

|type(4)flags(4)|[payload]

"""

import math
from typing import Any, List, Dict

class SHBinEncoder:
    def __init__(self, huffman_encoder, encode_integer):
        self.huffman_encode = huffman_encoder.encode
        self.encode_integer = encode_integer

    def serialise(self, input_data: Any) -> str:
        data_type = type(input_data)
        if data_type == dict:
            return self.ser_dictionary(input_data)
        if data_type == list and type(input_data[0]) == list:
            return self.ser_listlist(input_data)
        if data_type == list and type(input_data[0]) == tuple:
            return self.ser_paramlist(input_data)
        if data_type == list:
            return self.ser_list(input_data)
        if data_type in [str, int, float, bool, bytes]:
            return self.ser_item(input_data)
        raise ValueError("Unrecognised input data.")
    
    def ser_boolean(self, inval: bool) -> str:
        """
        type: 0x00
        payload: data(varint)
        """
        value = self.encode_integer(inval, 4)
        value[0] |= 0x00
        return value

    def ser_byteseq(self, byteseq: bytes) -> str:
        """
        type: 0x10
        payload: len(varint) value
        """
        length = len(byteseq)
        value = self.encode_integer(length, 4)
        value[0] |= 0x10
        return b''.join([value] + byteseq)

    def ser_string(self, inval: str) -> str:
        """
        type: 0x20
        payload: len(varint) data
        """
        length = len(inval)
        value = self.encode_integer(length, 4)
        value[0] |= 0x20
        value += self.huffman_encode(inval.encode('utf-8'))
        return value

    def ser_token(self, token: str) -> str:
        """
        type: 0x30
        payload: len(varint) data
        """
        length = len(inval)
        value = self.encode_integer(length, 4)
        value[0] |= 0x30
        value += self.huffman_encode(inval.encode('utf-8'))
        return value
    
    def ser_float(self, inval: float) -> str: # FIXME: negative
        """
        type: 0x40
        payload: 
        """
        int_val, frac_val = math.modf(inval)
        value = self.encode_integer(int(int_val), 4)
        value += self.encode_integer(int(("%f" % frac_val)[2:]), 8) # HACK
        value[0] |= 40
        return value

    def ser_integer(self, inval: int) -> str:  # FIXME: negative
        """
        type: 0x50
        payload: value(varint)
        """
        value = self.encode_integer(inval, 4)
        value[0] |= 0x50
        return value

    def ser_item(self, item: Any) -> str:
        item_type = type(item)
        if item_type not in [int, float, str, bytes, bool]:
            raise ValueError("Item type not recognised.")
        if item_type is int:
            return self.ser_integer(item)
        if item_type is float:
            return self.ser_float(item)
        if item_type is str:
            return self.ser_string(item)
        if item_type is str: # FIXME
            return self.ser_token(item)
        if item_type is bool:
            return self.ser_boolean(item)
        return self.ser_byteseq(item)
    
    def ser_list(self, input_list: List) -> str:
        """
        type: 0x60
        payload: num_items(varint) [item...]
        """
        num_items = len(input_list)
        value = self.encode_integer(num_items, 4)
        value[0] |= 0x60
        item_list = [self.ser_item(i) for i in input_list]
        return b''.join([value] + item_list)
    
    def ser_listlist(self, input_list: List[List]) -> str:
        """
        type: 0x70
        payload:
        """
        raise NotImplementedError # FIXME

    def ser_dictionary(self, input_dict: Dict) -> str:
        """
        type: 0x80
        payload: num_kvs(varint) (key val)+
        """
        num_kvs = len(input_dict)
        value = self.encode_integer(num_kvs, 4)
        value[0] |= 0x80
        for k,v in input_dict.items():
            value += self.ser_key(k)
            value += self.ser_item(v)
        return value

    def ser_key(self, inval):
        length = len(inval)
        value = self.encode_integer(length, 8)
        encoded_value = self.huffman_encode(inval.encode('utf-8'))
        value += encoded_value
        return value
    
    def ser_paramlist(self, input_list: List) -> str:
        """
        type: 0x90
        payload: 
        """
        num_items = len(input_list)
        value = self.encode_integer(num_items, 4)
        value[0] |= 0x90
        for i in input_list:
            primary_id = i[0]
            params = i[1]
            value += self.ser_key(primary_id)
            num_params = len(params)
            value += self.encode_integer(num_params, 8)
            for k,v in params.items():
                value += self.ser_key(k)
                value += self.ser_item(v)
        return value

