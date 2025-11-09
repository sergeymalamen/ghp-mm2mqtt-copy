import serial
import logging

_logger = logging.getLogger(__name__)

# Конфигурация порта
SERIAL_PORT = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BG009VVA-if00-port0"  # или другой путь, если используется другой адаптер
BAUDRATE = 9600

def init_serial():
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0  # blocking read
        )
        if ser.is_open:
            _logger.info(f"✅ Последовательный порт {ser.port} открыт успешно!")
            ser.reset_input_buffer()
            print(f"✅ Последовательный порт {ser.port} открыт успешно!")
            return ser
        else:
            raise serial.SerialException("❌ Не удалось открыть порт.")
    except serial.SerialException as e:
        _logger.error(f"Ошибка при открытии порта: {e}")
        raise