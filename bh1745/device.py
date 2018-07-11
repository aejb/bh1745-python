import smbus

bus = smbus.SMBus(1)

def _byte_swap(value):
    return (value >> 8) | ((value & 0xFF) << 8)

def _mask_width(value, bitwidth=8):
    value >>= _trailing_zeros(value, bitwidth)
    return value.bit_length()

def _leading_zeros(value, bitwidth=8):
    count = 0
    for x in range(bitwidth):
        if value & (1 << (bitwidth - 1)):
            return count
        count += 1
        value <<= 1
    return count

def _trailing_zeros(value, bitwidth=8):
    count = 0
    for x in range(bitwidth):
        if value & 1:
            return count
        count += 1
        value >>= 1
    return count

def _unmask(value, mask, bitwidth=16):
    output = 0
    shift = 0
    for x in range(bitwidth):
        if mask & (1 << x):
            output |= (value & (1 << x)) >> shift
        else:
            shift += 1

def _mask(value, mask, bitwidth=16):
    output = 0
    ptr = 1
    shift = 0
    for x in range(bitwidth):
        if mask & (1 << x):
            output |= (value & ptr) << shift
            ptr <<= 1
        else:
            shift += 1

def _int_to_bytes(value, length, endianness='big'):
    return value.to_bytes(length, endianness)

class Device():
    def __init__(self, i2c_address, i2c_dev=None, bitwidth=8):
        self._bitwidth = bitwidth
        self._i2c_address = i2c_address
        self._i2c = i2c_dev
        if self._i2c is None:
            import smbus
            self._i2c = smbus.SMBus(1)

    def write(self, register, value, bitwidth):
        values = _int_to_bytes(value, bitwidth // self._bitwidth, 'big')
        values = list(values)
        #values = [ord(x) for x in _int_to_bytes(value, bitwidth // self._bitwidth, 'big')]
        #print(("Writing: " + ("{:02x}" * len(values)) + " to register: 0x{:02x}").format(*values, register))
        bus.write_i2c_block_data(self._i2c_address, register, values)

    def read(self, register, bitwidth):
        value = 0
        for x in bus.read_i2c_block_data(self._i2c_address, register, bitwidth // self._bitwidth):
            value <<= 8
            value |= x
        #print(("Read value: 0b{:0" + str(bitwidth) + "b} from register: 0x{:02x}").format(value, register))
        return value
        
class Register():
    def __init__(self, device, address, fields={}, bitwidth=8, read_only=False, volatile=True):
        self._device = device
        self._address = address
        self._bitwidth = bitwidth
        self._fields = fields
        self._value = 0
        self._read_only = read_only
        self._volatile = volatile

        self.read()

        for field in self._fields:
            field._register = self

            if not field.read_only and not self._read_only:
                self.__dict__["set_{}".format(field.name)] = field.set

            self.__dict__["get_{}".format(field.name)] = field.get

    def get_value(self):
        return self._value

    def __trunc__(self):
        return self.get_value()

    def __repr__(self):
        return ("0b{:0" + str(self._bitwidth) + "b}").format(self.get_value())

    def strr__(self):
        return "Register object with value: {}".format(self.__repr__())

    def read(self):
        if self._value == 0 or self._volatile:
            self._value = self._device.read(self._address, self._bitwidth)

    def write(self):
        self._device.write(self._address, self._value, self._bitwidth)

    def set_bits(self, mask, value):
        self._value = (self._value & ~mask) | (value << _trailing_zeros(mask, self._bitwidth) & mask)

    def get_bits(self, mask):
        return (self._value & mask) >> _trailing_zeros(mask, self._bitwidth)

class BitField():
    def __init__(self, name, mask, values_map={}, values_in=None, values_out=None, bitwidth=8, read_only=False):
        self._mask = mask
        self._values_map = values_map
        self._register = None
        self._values_in = values_in
        self._values_out = values_out

        self.name = name
        self.read_only = read_only

    def set(self, value, write=True):
        value = self._remap_value_in(value)
        self._register.set_bits(self._mask, value)
        if write:
            self._register.write()

    def get(self, read=True):
        if read:
            self._register.read()
        return self._remap_value_out(self._register.get_bits(self._mask))

    def _remap_value_out(self, value):
        if callable(self._values_out):
            return self._values_out(value)

        if len(self._values_map) == 0:
            return value

        try:
            return list(self._values_map.keys())[list(self._values_map.values()).index(value)]
        except KeyError:
            raise ValueError("")

    def _remap_value_in(self, value):
        if callable(self._values_in):
            return self._values_in(value)

        if len(self._values_map) == 0:
            return value

        try:
            return self._values_map[value]
        except KeyError:
            raise ValueError("Invalid value for {}: \"{}\". Valid values: {}".format(self.name, value, ', '.join([str(v) for v in self._values_map.keys()])))

