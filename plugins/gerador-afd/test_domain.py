import unittest
import importlib.util
from pathlib import Path

_domain_path = Path(__file__).parent / "domain.py"
_spec = importlib.util.spec_from_file_location("gerador_afd_domain", _domain_path)
domain = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(domain)

calcular_crc16 = domain.calcular_crc16
limpar_numero = domain.limpar_numero
pad_left = domain.pad_left
pad_right = domain.pad_right
gerar_afd = domain.gerar_afd
nome_arquivo = domain.nome_arquivo
process_gerar_afd = domain.process_gerar_afd


class TestGeradorAfdDomain(unittest.TestCase):
    def test_crc16_calculation(self):
        crc = calcular_crc16("123456789")
        self.assertEqual(len(crc), 4)
        self.assertTrue(all(c in "0123456789ABCDEF" for c in crc))

    def test_helpers(self):
        self.assertEqual(limpar_numero("12.345.678/0001-95"), "12345678000195")
        self.assertEqual(pad_left("42", 5), "00042")
        self.assertEqual(pad_right("Empresa", 10), "Empresa   ")
