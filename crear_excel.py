import pandas as pd

columnas = ["mes", "ventas", "coste_ventas", "gasto_marketing",
            "clientes_nuevos", "pedidos", "pedidos_retrasados", "renuncias"]

filas = [
    ("ene", 110000, 63000, 21000, 55, 380,  30, 0),
    ("feb", 112000, 64000, 21000, 56, 385,  32, 0),
    ("mar", 108000, 62000, 20000, 54, 370,  31, 1),
    ("abr", 105000, 58000, 20000, 52, 360,  34, 0),
    ("may", 100000, 58000, 20000, 50, 365,  36, 0),
    ("jun",  95000, 58000, 20000, 48, 375,  40, 0),
    ("jul",  90000, 55000, 19000, 42, 320,  90, 0),
    ("ago",  85000, 56000, 19000, 40, 330, 100, 0),
    ("sep",  80000, 55000, 20000, 38, 350, 110, 2),
]

df = pd.DataFrame(filas, columns=columnas)
df.to_excel("datos_empresa.xlsx", index=False)
print("Excel de prueba creado: datos_empresa.xlsx")