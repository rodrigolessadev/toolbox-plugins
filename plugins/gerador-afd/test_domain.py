#!/usr/bin/env python3
import unittest
from main import (
    calcular_crc16,
    limpar_numero,
    pad_left,
    pad_right,
    gerar_afd,
    nome_arquivo,
    process_gerar_afd,
)


class TestGeradorAfdDomain(unittest.TestCase):
    def test_crc16_calculation(self):
        # Test standard CRC16 CCITT XModem string
        crc = calcular_crc16("123456789")
        self.assertEqual(len(crc), 4)
        self.assertTrue(all(c in "0123456789ABCDEF" for c in crc))

    def test_helpers(self):
        self.assertEqual(limpar_numero("12.345.678/0001-95"), "12345678000195")
        self.assertEqual(pad_left("42", 5), "00042")
        self.assertEqual(pad_right("Empresa", 10), "Empresa   ")

    def test_nome_arquivo(self):
        nome = nome_arquivo("00000000000000001", "12.345.678/0001-95")
        self.assertEqual(nome, "AFD0000000000000000112345678000195REP_C.TXT")


    def test_gerar_afd_structure(self):
        colaboradores = [
            {"cpf": "12345678901", "horarios": ["08:00", "12:00"]}
        ]
        content = gerar_afd(
            rep_number="1",
            cnpj="12345678000195",
            razao_social="Empresa Teste",
            data_inicial="2025-04-01",
            data_final="2025-04-01",
            colaboradores=colaboradores,
        )
        lines = [l for l in content.split("\r\n") if l]

        # Tipo 1 (Header), Tipo 2 (Establishment), Tipo 3 (2 records: 08:00 & 12:00), Tipo 9 (Trailer) -> 5 lines
        self.assertEqual(len(lines), 5)
        self.assertTrue(lines[0].startswith("0000000001"))  # Tipo 1
        self.assertTrue(lines[1].startswith("0000000012"))  # Tipo 2 (NSR 1)
        self.assertTrue(lines[2].startswith("0000000023"))  # Tipo 3 (NSR 2)
        self.assertTrue(lines[3].startswith("0000000033"))  # Tipo 3 (NSR 3)
        self.assertTrue(lines[4].startswith("999999999000000001"))  # Tipo 9 (Trailer)

    def test_process_gerar_afd_success(self):
        res = process_gerar_afd(
            rep_number="1",
            cnpj="12345678000195",
            razao_social="Empresa Teste",
            data_inicial="2025-04-01",
            data_final="2025-04-01",
            colaboradores=[{"cpf": "123.456.789-00", "horarios": ["08:00"]}],
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["total_records"], 4)
        self.assertIn("Empresa Teste", res["content"])

    def test_process_gerar_afd_validation_failures(self):
        # Missing REP
        res = process_gerar_afd("", "12345678000195", "Razao", "2025-01-01", "2025-01-01", [{"cpf": "1"}])
        self.assertFalse(res["success"])
        self.assertIn("REP é obrigatório", res["error"])

        # Empty colaboradores
        res = process_gerar_afd("1", "12345678000195", "Razao", "2025-01-01", "2025-01-01", [])
        self.assertFalse(res["success"])
        self.assertIn("colaborador deve ser informado", res["error"])


if __name__ == "__main__":
    unittest.main()
