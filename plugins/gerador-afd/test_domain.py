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

    def test_gerar_afd_execution(self):
        res = gerar_afd(
            rep_number="123",
            cnpj_cpf="12345678000195",
            razao_social="Empresa Teste",
            local_prestacao="Matriz",
            pis="12345678901",
            nome_empregado="Funcionario",
            start_date="2026-08-20",
            end_date="2026-08-21",
            horarios=["08:00", "12:00"]
        )
        self.assertTrue(res["success"])
        self.assertGreater(res["total_records"], 0)
        self.assertIn("12345678000195", res["filename"])

    def test_file_clock_icon_and_taskbar_helper(self):
        icon_path = domain.FILE_CLOCK_ICON_PATH
        self.assertTrue(icon_path.exists())
        self.assertEqual(icon_path.suffix, ".ico")
        self.assertGreater(icon_path.stat().st_size, 0)
        res = domain.set_window_taskbar_icon(icon_path=icon_path, hwnd=None)
        self.assertIsInstance(res, bool)

