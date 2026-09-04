import sqlite3
from pathlib import Path
from .config import DB_PATH


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = connect()
    con.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        order_id TEXT NOT NULL UNIQUE,
        amount_rial INTEGER NOT NULL,
        status TEXT NOT NULL,
        token TEXT,
        invoice_no TEXT,
        trans_no TEXT,
        ref_no TEXT,
        trace_no TEXT,
        message TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    con.commit(); con.close()


def create_payment(user_id: int, order_id: str, amount_rial: int):
    con = connect()
    con.execute('INSERT INTO payments(user_id,order_id,amount_rial,status) VALUES(?,?,?,?)',
                (user_id, order_id, amount_rial, 'pending'))
    con.commit(); con.close()


def get_payment(order_id: str):
    con = connect(); row = con.execute('SELECT * FROM payments WHERE order_id=?', (order_id,)).fetchone(); con.close(); return row


def set_token(order_id: str, token: str, invoice_no: str):
    con = connect(); con.execute("UPDATE payments SET token=?, invoice_no=?, updated_at=CURRENT_TIMESTAMP WHERE order_id=?", (token, invoice_no, order_id)); con.commit(); con.close()


def set_result(order_id: str, status: str, message: str = '', **fields):
    allowed = {'trans_no','ref_no','trace_no'}
    sets = ['status=?','message=?','updated_at=CURRENT_TIMESTAMP']; vals=[status,message]
    for k,v in fields.items():
        if k in allowed:
            sets.append(f'{k}=?'); vals.append(v)
    vals.append(order_id)
    con=connect(); con.execute(f"UPDATE payments SET {', '.join(sets)} WHERE order_id=?", vals); con.commit(); con.close()
