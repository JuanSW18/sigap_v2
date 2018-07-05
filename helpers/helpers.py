from zipfile import ZipFile
from .campos_excel import formato_one, formato_two
import psycopg2 as ps
import pandas as pd

conn = ps.connect("host=localhost dbname=tcs_prueba user=postgres password=1234")
# conn = ps.connect("host=159.65.102.15 dbname=tcs user=postgres password=arquisoftware123")
cur = conn.cursor()

name_of_pc = ""
ip = ""
good_files = []
bad_files = []
total_registros_procesados = 0
formato_excel = {}
status_indiv_file = 'OK'
msg_error_column = 'El formato del excel no contiene la columna'

def process_zip_file(path_zip_file, filename, tipo_formato, uploader):
    if tipo_formato == 1:
        formato_excel = formato_one
    if tipo_formato == 2:
        formato_excel = formato_two
    archivo_zip = ZipFile(path_zip_file, 'r')
    content_of_zip = archivo_zip.infolist()
    good_files = []
    bad_files = []
    for s in content_of_zip:
        if s.filename.endswith('.xls'):
            try:
                df = pd.read_excel(archivo_zip.open(
                    s.filename, 'r'), converters=formato_excel)
                process_df = df[df.DEPENDENCIA.notnull()]
                df_final = process_df.fillna(0)
                nro_registros = save_registers_in_database(
                    df_final, s.filename)
                good_files.append(
                    {'file': s.filename, 'nro_registros': nro_registros})
                global total_registros_procesados
                total_registros += nro_registros
            except AttributeError as e:
                indice = str(e).find('attribute')
                global msg_error_column
                error = msg_error_column + str(e)[indice + 9:]
                bad_files.append(
                    {'file': s.filename, 'problema': error})
                save_file_upload_error(s.filename, error)


def process_excel_file(path_excel_file, tipo_formato):
    # Por esto salia error, el formato no estaba definido
    if tipo_formato == 1:
        formato_excel = formato_one
    if tipo_formato == 2:
        formato_excel = formato_two
    try:
        df = pd.read_excel(path_excel_file, converters=formato_excel)
        process_df = df[df.DEPENDENCIA.notnull()]
        df_final = process_df.fillna(0)
        nro_registros = save_registers_in_database(
            df_final, path_excel_file[8:])
        # remove(path_excel_file)
        return nro_registros
    except AttributeError as e:
        save_file_upload_error(path_excel_file[8:], str(e))
        indice = str(e).find('attribute')
        global msg_error_column
        error = msg_error_column + str(e)[indice + 9:]
        # status_indiv_file = f"ERROR: {error}"
        global status_indiv_file
        status_indiv_file = "ERROR: " + error
        # remove(path_excel_file)
        return 0


def save_registers_in_database(df, filename, tipo_formato):
    # if aqui codigo para cambiar campo MODENA COD.
    save_data_for_auditoria(filename)
    contador = 0
    if tipo_formato == 1:
        for fila in df.itertuples():
            register = (fila.MONEDA, fila.DEPENDENCIA, fila.CONCEP, fila.a, fila.b,
                        fila.NUMERO, fila.CODIGO, fila.NOMBRE, fila.IMPORTE, fila.CARNET,
                        fila.AUTOSEGURO, fila.AVE, fila._13, fila.OBSERVACIONES, fila.FECHA)
            save_register(register)
            contador += 1
    if tipo_formato == 2:
        for fila in df.itertuples():
            register = (fila._1, fila.DEPENDENCIA, fila.CONCEP, fila.a, fila.b,
                        fila.NUMERO, fila.CODIGO, fila.NOMBRE, fila.IMPORTE, fila.CARNET,
                        fila.AUTOSEGURO, fila.AVE, fila._13, fila.OBSERVACIONES, fila.FECHA)
            save_register(register)
            contador += 1
    return contador


def save_register(register):
    if not existe(register):
        save_register_valid(register)
        cur.execute(
            "SELECT id_raw FROM recaudaciones_raw ORDER BY id_raw DESC limit 1")
        id_rec = cur.fetchall()
        fecha_raw = register[14]
        fecha = fecha_raw[:4] + '-' + fecha_raw[4:6] + '-' + fecha_raw[6:]
        save_recaudaciones_normalizada(fecha, id_rec[0])


def save_recaudaciones_normalizada(fecha, id_rec):
    query = "UPDATE recaudaciones SET fecha=%s WHERE id_rec=%s"
    update = (fecha, id_rec)
    cur.execute(query, update)
    conn.commit()


def save_data_for_auditoria(filename):
    global ip
    query = "INSERT INTO registro_carga(nombre_equipo, ip, ruta) VALUES(%s, %s, %s)"
    global name_of_pc
    update = (name_of_pc, ip, filename)
    cur.execute(query, update)
    conn.commit()


def save_register_valid(register):
    query = "INSERT INTO recaudaciones_raw(moneda, dependencia, concep, concep_a, concep_b, numero, codigo, nombre, importe, carnet, autoseguro, ave, devol_tran, observacion, fecha) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    cur.execute(query, register)
    conn.commit()


def existe(register):
    query = "SELECT count(*) FROM recaudaciones_raw where moneda=%s AND dependencia=%s AND concep=%s AND concep_a=%s AND concep_b=%s AND numero=%s AND codigo=%s AND nombre=%s AND importe=%s AND fecha=%s;"
    data = (register[0], register[1], register[2], register[3], register[4],
            register[5], register[6], register[7], str(register[8]), register[14])
    cur.execute(query, data)
    flag = cur.fetchall()
    if int(flag[0][0]) == 1:
        return True
    return False


def save_bad_files(self):
    return True


def save_file_upload_error(filename, error):
    query = "INSERT INTO recaudaciones_fallidas(nombre_archivo, descripcion_error) VALUES (%s, %s)"
    data = (filename, error)
    cur.execute(query, data)
    conn.commit()
