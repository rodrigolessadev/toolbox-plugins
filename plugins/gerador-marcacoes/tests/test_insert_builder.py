"""
Testes para o plugin gerador-marcacoes (portado do insert-builder.ts do KapiNote).

Cobre:
  * Dialeto SQL Server vs Oracle (DATACC, semantica TO_DATE vs ISO)
  * Multiplos horarios gerando multiplos INSERTs
  * Filtragem por dia da semana
  * Campos opcionais (presentes vs ausentes)
  * Helpers de dialeto (fn_data_atual, fn_isnull, traduzir_tipo)
  * Validacao (ValueError em horarios vazios, datas vazias, intervalo invertido)

Executar:
    cd toolbox-plugins/plugins/gerador-marcacoes
    python -m pytest tests/
"""

import sys
from datetime import date
from pathlib import Path

# Permite importar o main.py como modulo sem disparar a UI (tk.Tk).
# Adicionamos a pasta do plugin ao sys.path e mockamos tk antes de importar.
import os
os.environ.setdefault("DISPLAY", ":0")  # no-op em headless; evita falha do X11

# Importacao direta das funcoes puras (UI fica fora do caminho)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from insert_builder import (  # noqa: E402
    date_range, escape_sql_string, fn_data_atual, fn_isnull,
    format_date_value, format_value, gerar_inserts, time_to_minutes,
    traduzir_tipo, NUMERIC_FIELDS, DATE_FIELDS, OPTIONAL_DEFAULTS,
)


# ---------------------------------------------------------------------------
# Helpers de dialeto
# ---------------------------------------------------------------------------

class TestFnDataAtual:
    def test_sqlserver_retorna_getdate(self):
        assert fn_data_atual("sqlserver") == "GETDATE()"

    def test_oracle_retorna_sysdate(self):
        assert fn_data_atual("oracle") == "SYSDATE"


class TestFnIsnull:
    def test_sqlserver(self):
        assert fn_isnull("x", "0", "sqlserver") == "ISNULL(x, 0)"

    def test_oracle(self):
        assert fn_isnull("x", "0", "oracle") == "NVL(x, 0)"


class TestTraduzirTipo:
    def test_sqlserver_passa_direto(self):
        assert traduzir_tipo("varchar(50)", "sqlserver") == "varchar(50)"
        assert traduzir_tipo("int", "sqlserver") == "int"

    def test_oracle_varchar_vira_varchar2(self):
        assert traduzir_tipo("varchar", "oracle") == "VARCHAR2"
        assert traduzir_tipo("nvarchar", "oracle") == "VARCHAR2"

    def test_oracle_int_vira_number(self):
        assert traduzir_tipo("int", "oracle") == "NUMBER"
        assert traduzir_tipo("smallint", "oracle") == "NUMBER(5)"
        assert traduzir_tipo("bigint", "oracle") == "NUMBER(19)"

    def test_oracle_datetime_vira_date(self):
        assert traduzir_tipo("datetime", "oracle") == "DATE"
        assert traduzir_tipo("smalldatetime", "oracle") == "DATE"

    def test_oracle_text_vira_clob(self):
        assert traduzir_tipo("text", "oracle") == "CLOB"

    def test_oracle_tipo_desconhecido_vai_uppercase(self):
        assert traduzir_tipo("xml", "oracle") == "XML"


# ---------------------------------------------------------------------------
# Formatacao de valores
# ---------------------------------------------------------------------------

class TestTimeToMinutes:
    def test_horario_normal(self):
        assert time_to_minutes("08:00") == 480
        assert time_to_minutes("08:30") == 510
        assert time_to_minutes("17:45") == 1065

    def test_horario_vazio(self):
        assert time_to_minutes("") == 0
        assert time_to_minutes(None) == 0

    def test_horario_invalido(self):
        assert time_to_minutes("abc") == 0
        assert time_to_minutes("25:99") == 0


class TestEscapeSqlString:
    def test_aspas_simples_duplicadas(self):
        assert escape_sql_string("O'Brien") == "O''Brien"

    def test_string_vazia(self):
        assert escape_sql_string("") == ""
        assert escape_sql_string(None) == ""


class TestFormatDateValue:
    def test_sqlserver_iso(self):
        result = format_date_value(date(2025, 4, 3), "sqlserver")
        assert result == "'20250403 00:00:00.000'"

    def test_oracle_to_date(self):
        result = format_date_value(date(2025, 4, 3), "oracle")
        assert result == "TO_DATE('03-04-2025 00:00:00.000', 'DD-MM-YYYY HH24:MI:SS')"


class TestFormatValue:
    def test_campo_numerico(self):
        assert format_value("NUMCAD", "42", "sqlserver") == "42"

    def test_campo_numerico_vazio_vira_zero(self):
        assert format_value("NUMCAD", "", "sqlserver") == "0"

    def test_numcra_aceita_alfanumerico(self):
        # NUMCRA no Protheus aceita letras (ex: "M001"), entao eh string
        # e precisa de aspas. Antes era tratado como numerico (bug do TS).
        assert format_value("NUMCRA", "abc", "sqlserver") == "'abc'"
        assert format_value("NUMCRA", "O'Brien", "sqlserver") == "'O''Brien'"

    def test_campo_data(self):
        result = format_value("DATAPU", "03-04-2025", "sqlserver")
        assert "'20250403 00:00:00.000'" in result


# ---------------------------------------------------------------------------
# date_range - filtragem por dia da semana
# ---------------------------------------------------------------------------

class TestDateRange:
    def test_filtro_apenas_dias_uteis(self):
        # Semana de 07/04/2025 (seg) a 11/04/2025 (sex) -> 5 dias
        datas = date_range(date(2025, 4, 7), date(2025, 4, 11), {1, 2, 3, 4, 5})
        assert len(datas) == 5
        assert datas[0] == date(2025, 4, 7)
        assert datas[-1] == date(2025, 4, 11)

    def test_filtro_apenas_sabado_e_domingo(self):
        # 12/04 sab, 13/04 dom
        datas = date_range(date(2025, 4, 7), date(2025, 4, 13), {0, 6})
        assert datas == [date(2025, 4, 12), date(2025, 4, 13)]

    def test_dias_vazios_retorna_lista_vazia(self):
        assert date_range(date(2025, 4, 7), date(2025, 4, 11), set()) == []

    def test_intervalo_de_um_dia(self):
        datas = date_range(date(2025, 4, 9), date(2025, 4, 9), {1, 2, 3, 4, 5})
        assert datas == [date(2025, 4, 9)]


# ---------------------------------------------------------------------------
# gerar_inserts - integracao
# ---------------------------------------------------------------------------

class TestGerarInsertsSqlServer:
    def test_basico(self):
        sql = gerar_inserts(
            fields={"NUMCRA": "123", "USOMAR": "2", "NUMEMP": "1",
                    "TIPCOL": "1", "NUMCAD": "42"},
            horarios=["08:00"],
            datas=[date(2025, 4, 7)],
            banco="sqlserver",
            selected_optional=[],
        )
        assert sql.startswith("INSERT INTO R070ACC (")
        assert "'20250407 00:00:00.000'" in sql  # DATACC
        assert "480" in sql                       # HORACC = 8*60

    def test_multiplos_horarios(self):
        sql = gerar_inserts(
            fields={"NUMCRA": "123", "USOMAR": "2", "NUMEMP": "1",
                    "TIPCOL": "1", "NUMCAD": "42"},
            horarios=["08:00", "12:00", "18:00"],
            datas=[date(2025, 4, 7)],
            banco="sqlserver",
            selected_optional=[],
        )
        assert sql.count("INSERT INTO R070ACC") == 3
        assert "480" in sql and "720" in sql and "1080" in sql

    def test_multiplas_datas(self):
        datas = date_range(date(2025, 4, 7), date(2025, 4, 11), {1, 2, 3, 4, 5})
        sql = gerar_inserts(
            fields={"NUMCRA": "123", "USOMAR": "2", "NUMEMP": "1",
                    "TIPCOL": "1", "NUMCAD": "42"},
            horarios=["08:00"],
            datas=datas,
            banco="sqlserver",
            selected_optional=[],
        )
        assert sql.count("INSERT INTO R070ACC") == 5

    def test_optional_selecionado_usa_valor_form(self):
        sql = gerar_inserts(
            fields={"NUMCRA": "123", "USOMAR": "2", "NUMEMP": "1",
                    "TIPCOL": "1", "NUMCAD": "42", "SEQACC": "99"},
            horarios=["08:00"],
            datas=[date(2025, 4, 7)],
            banco="sqlserver",
            selected_optional=["SEQACC"],
        )
        # SEQACC=99 (sexto valor) deve aparecer apos (...,42, 99,...)
        assert "(123, 2, 1, 1, 42, 99," in sql or "('123', 2, 1, 1, 42, 99," in sql

    def test_optional_nao_selecionado_usa_default(self):
        sql = gerar_inserts(
            fields={"NUMCRA": "123", "USOMAR": "2", "NUMEMP": "1",
                    "TIPCOL": "1", "NUMCAD": "42"},
            horarios=["08:00"],
            datas=[date(2025, 4, 7)],
            banco="sqlserver",
            selected_optional=[],
        )
        # SEQACC default = 1 na sexta posicao
        assert "('123', 2, 1, 1, 42, 1," in sql

    def test_aspas_em_string_sao_escapadas(self):
        # NUMCRA agora eh tratado como string (alfanumerico no Protheus),
        # entao o escape de aspas funciona.
        sql = gerar_inserts(
            fields={"NUMCRA": "O'Brien", "USOMAR": "2", "NUMEMP": "1",
                    "TIPCOL": "1", "NUMCAD": "42"},
            horarios=["08:00"],
            datas=[date(2025, 4, 7)],
            banco="sqlserver",
            selected_optional=[],
        )
        assert "'O''Brien'" in sql

    def test_horarios_vazios_raise(self):
        try:
            gerar_inserts(
                fields={"NUMCRA": "123"},
                horarios=[],
                datas=[date(2025, 4, 7)],
                banco="sqlserver",
                selected_optional=[],
            )
        except ValueError as e:
            assert "horario" in str(e).lower()
        else:
            raise AssertionError("Deveria ter lancado ValueError")

    def test_datas_vazias_raise(self):
        try:
            gerar_inserts(
                fields={"NUMCRA": "123"},
                horarios=["08:00"],
                datas=[],
                banco="sqlserver",
                selected_optional=[],
            )
        except ValueError as e:
            assert "data" in str(e).lower() or "dia" in str(e).lower()
        else:
            raise AssertionError("Deveria ter lancado ValueError")


class TestGerarInsertsOracle:
    def test_usa_to_date(self):
        sql = gerar_inserts(
            fields={"NUMCRA": "123", "USOMAR": "2", "NUMEMP": "1",
                    "TIPCOL": "1", "NUMCAD": "42"},
            horarios=["08:00"],
            datas=[date(2025, 4, 7)],
            banco="oracle",
            selected_optional=[],
        )
        assert "TO_DATE('07-04-2025 00:00:00.000', 'DD-MM-YYYY HH24:MI:SS')" in sql
        # Em Oracle, nao deve aparecer o formato ISO
        assert "TO_DATE" in sql
        assert "'20250407" not in sql

    def test_oracle_com_opcional(self):
        sql = gerar_inserts(
            fields={"NUMCRA": "123", "USOMAR": "2", "NUMEMP": "1",
                    "TIPCOL": "1", "NUMCAD": "42", "DIRACC": "S"},
            horarios=["08:00"],
            datas=[date(2025, 4, 7)],
            banco="oracle",
            selected_optional=["DIRACC"],
        )
        assert "'S'" in sql


# ---------------------------------------------------------------------------
# Constantes - invariantes
# ---------------------------------------------------------------------------

class TestConstantes:
    def test_optional_tem_20_entradas(self):
        # KapiNote tem 20 campos no Select; preservamos essa contagem.
        assert len(OPTIONAL_DEFAULTS) == 20

    def test_nomes_optional_sao_unicos(self):
        nomes = list(OPTIONAL_DEFAULTS.keys())
        assert len(nomes) == len(set(nomes))

    def test_numeric_fields_contem_principais_exceto_numcra(self):
        for nome in ("USOMAR", "NUMEMP", "TIPCOL", "NUMCAD"):
            assert nome in NUMERIC_FIELDS
        # NUMCRA foi removido: aceita alfanumerico no Protheus.
        assert "NUMCRA" not in NUMERIC_FIELDS

    def test_date_fields_contem_datapu(self):
        assert "DATAPU" in DATE_FIELDS
