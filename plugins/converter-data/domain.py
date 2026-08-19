from datetime import datetime, timezone, timedelta

def to_excel_serial(date_str: str, time_str: str) -> float:
    try:
        parts = [int(p) for p in date_str.split("-")]
        if len(parts) != 3:
            return 0.0
        y, m, d = parts
        h, mn, s = 0, 0, 0
        if time_str:
            tparts = [int(p) for p in time_str.split(":")]
            if len(tparts) >= 2:
                h, mn = tparts[0], tparts[1]
                s = tparts[2] if len(tparts) > 2 else 0
        dt = datetime(y, m, d, h, mn, s)
        base = datetime(1899, 12, 30)
        delta = dt - base
        return delta.days + (delta.seconds / 86400.0)
    except Exception:
        return 0.0

def convert_timestamp(val_str: str) -> dict:
    val_str = val_str.strip()
    if not val_str:
        return {"success": False, "message": "Informe um valor."}
    try:
        num = float(val_str)
        # Se for milissegundos
        if num > 1e11:
            sec = num / 1000.0
        else:
            sec = num
        dt_utc = datetime.fromtimestamp(sec, tz=timezone.utc)
        dt_local = datetime.fromtimestamp(sec)
        excel = to_excel_serial(dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%H:%M:%S"))
        return {
            "success": True,
            "epoch_sec": int(sec),
            "epoch_ms": int(sec * 1000),
            "iso_utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "iso_local": dt_local.strftime("%Y-%m-%d %H:%M:%S"),
            "br_local": dt_local.strftime("%d/%m/%Y %H:%M:%S"),
            "excel": f"{excel:.5f}"
        }
    except Exception:
        # Tenta converter de data para timestamp
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                dt = datetime.strptime(val_str, fmt)
                sec = dt.timestamp()
                return {
                    "success": True,
                    "epoch_sec": int(sec),
                    "epoch_ms": int(sec * 1000),
                    "iso_utc": datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "iso_local": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "br_local": dt.strftime("%d/%m/%Y %H:%M:%S"),
                    "excel": f"{to_excel_serial(dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M:%S')):.5f}"
                }
            except Exception:
                continue
        return {"success": False, "message": "Formato inválido. Use timestamp (ex: 1771500000) ou data (ex: 2026-08-19 14:00:00)."}
