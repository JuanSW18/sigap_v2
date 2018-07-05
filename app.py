# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, json
from flask_cors import CORS
from zipfile import ZipFile
from helpers.campos_excel import formato_one, formato_two
import psycopg2 as ps
import pandas as pd
import os

app = Flask(__name__)
cors = CORS(app, resources={r"/*": {"origins": "*"}})
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

name_of_pc = ""
ip = ""
total_registros_procesados = 0
total_registros_insertados = 0
total_registros_excluidos = 0
good_files = []
bad_files = []
duplicados = []
insertados = []
isRepollo=""
status_indiv_file = 'OK'
individual_file_error = ''
msg_error_column = 'El formato del excel no contiene la columna'

# Funcion que define la repuesta 
# cuando se ingresa a traves del 
# navegador a la direccion ip:5000
@app.route('/')
def hello_world():
    return '<h1>Team Alphazero - Módulo Carga</h1>' \
           '<h3>Integrantes:</h3>' \
           '<ul>' \
           '<li>Caballero Fonseca, Raul Omar <b>(Backend)</b> </li>' \
           '<li> Ccopa Mamani, Andres Junior <b>(Frontend)</b> </li>' \
           '<li>Caillahua Castillo, Maria Katherine <b>(QA)</b> </li>' \
           '<li>Diaz Alvarran, Jorge <b>(DBA)</b> </li>' \
           '<li>Eneque Pisfil, Juan Rolando <b>(Backend)</b> </li>' \
           '</ul>'

# Metodo POST que será usado desde el FRONT
# para enviar el archivo (excel o zip) a procesar
@app.route('/upload', methods=['POST'])
def upload():
    target = os.path.join(APP_ROOT, "static/")
    # checking if the file is present or not.
    if 'file' not in request.files:
        return "No file found"

    if not os.path.isdir(target):
        os.mkdir(target)
        global name_of_pc, ip

    file = request.files['file']
    tipo_archivo = request.form.get('tipo')
    name_of_pc = request.form.get('name')
    ip = "200.48.225.130"
    formato = request.form.get('formato')
    respuesta = {}

    filename = file.filename
    destination = "/".join([target, filename])
    file.save(destination)

    if tipo_archivo == "zip":
        global total_registros_procesados, total_registros_insertados, total_registros_excluidos
        total_registros_procesados = 0
        total_registros_insertados = 0
        total_registros_excluidos = 0
        process_zip_file(destination, filename, int(formato))
        global good_files, bad_files, duplicados, insertados
        respuesta = {'file': filename, 'good_files': {'lista_detalle': good_files, 'total_registros_procesados': total_registros_procesados, 'total_registros_insertados': total_registros_insertados,
                     'total_registros_excluidos': total_registros_excluidos}, 'bad_files': bad_files, 'no_procesados': len(bad_files), 'si_procesados': len(good_files)}
        os.remove(destination)
        return jsonify(respuesta)
    if tipo_archivo == "excel":
        #global duplicados
        global status_indiv_file
        status_indiv_file = "OK"
        reg_procesados, reg_insertados, reg_excluidos = process_excel_file(destination, filename, int(formato))
        respuesta = {'filename': filename, 'status': status_indiv_file, 'registros_procesados': reg_procesados, 'registros_insertados': reg_insertados,
                     'registros_excluidos': reg_excluidos, 'registros_duplicados_detalle': duplicados, 'registros_insertados_detalle': insertados}
        os.remove(destination)
        return jsonify(respuesta)

# Funcion para la conexion con la base de datos
def connect_database():
    return ps.connect(host="159.65.230.188", port=5432, dbname="tcs2", user="postgres", password="sigap789")

# Funcion para procesar archivos tipo zip
def process_zip_file(path_zip_file, filename, formato):
    global total_registros_procesados, total_registros_insertados, total_registros_excluidos, msg_error_column, good_files, bad_files, duplicados, insertados
    formato_excel = set_formato_excel(formato)

    archivo_zip = ZipFile(path_zip_file, 'r')
    content_of_zip = archivo_zip.infolist()
    good_files = []
    bad_files = []
    duplicados = []
    insertados = []
    extension = (".xls",".xlsx")
    for s in content_of_zip:
        duplicados = []
        insertados = []
        if s.filename.endswith(extension):
            print(s.filename)
            try:
                df = pd.read_excel(archivo_zip.open(s.filename, 'r'), converters=formato_excel)
                process_df = df[df.FECHA.notnull()]
                df_final = process_df.fillna(0)
                reg_procesados, reg_insertados, reg_excluidos = save_registers_in_database(df_final, s.filename, formato, duplicados, insertados)
                good_files.append({'filename': s.filename, 'status': status_indiv_file, 'registros_procesados': reg_procesados, 'registros_insertados': reg_insertados,
                     'registros_excluidos': reg_excluidos, 'registros_duplicados_detalle': duplicados, 'registros_insertados_detalle': insertados})
                total_registros_procesados += reg_procesados
                total_registros_insertados += reg_insertados
                total_registros_excluidos += reg_excluidos
            except AttributeError as e:
                indice = str(e).find('attribute')
                error = msg_error_column + str(e)[indice + 9:]
                bad_files.append(
                    {'file': s.filename, 'problema': error})
                save_file_upload_error(s.filename, error)

# Funcion para procesar archivos tipo excel
def process_excel_file(path_excel_file, filename, formato):
    global duplicados, insertados
    duplicados = []
    insertados = []
    formato_excel = set_formato_excel(formato)
    try:
        df = pd.read_excel(path_excel_file, converters=formato_excel)
        process_df = df[df.FECHA.notnull()]
        df_final = process_df.fillna(0)
        reg_procesados, reg_insertados, reg_excluidos = save_registers_in_database(df_final, filename, formato, duplicados, insertados)
        return reg_procesados, reg_insertados, reg_excluidos
    except AttributeError as e:
        save_file_upload_error(filename, str(e))
        indice = str(e).find('attribute')
        global msg_error_column, status_indiv_file
        nombre_campo = cabecera_a_texto(str(e)[indice + 10:])
        error = msg_error_column + ' ' + nombre_campo
        status_indiv_file = error
        return 0, 0, 0

# Funcion donde se establecen los campos que seran guardados en la base de datos
def save_registers_in_database(df, filename, formato, duplicados, insertados):
    reg_insertados = 0
    reg_procesados = 0
    conn = connect_database()
    cur = conn.cursor()
    save_data_for_auditoria(filename, cur)
    if formato == 1:
        for fila in df.itertuples():
            register = (fila.MONEDA, fila.DEPENDENCIA, fila.CONCEP, fila.a, fila.b,
                        fila.NUMERO, fila.CODIGO, fila.NOMBRE, fila.IMPORTE, fila.CARNET,
                        fila.AUTOSEGURO, fila.AVE, fila._13, fila.OBSERVACIONES, fila.FECHA)
            flag = save_register(register, cur, duplicados, filename, insertados)
            reg_procesados += 1
            if flag == 1:
                reg_insertados += 1
        conn.commit()
        conn.close()
    elif formato == 2:
        for fila in df.itertuples():
            register = (fila._1, fila.DEPENDENCIA, fila.CONCEP, fila.a, fila.b,
                        fila.NUMERO, fila.CODIGO, fila.NOMBRE, fila.IMPORTE, fila.CARNET,
                        fila.AUTOSEGURO, fila.AVE, fila._13, fila.OBSERVACIONES, fila.FECHA)
            flag = save_register(register, cur, duplicados, filename, insertados)
            reg_procesados += 1
            if flag == 1:
                reg_insertados += 1
        conn.commit()
        conn.close()
    reg_excluidos = reg_procesados - reg_insertados
    return reg_procesados, reg_insertados, reg_excluidos

# Funcion desde la cual 
# Solo se guardaran los registro si y solo si es la primera vez que se procesan
# es decir, no son duplicados
def save_register(register, cur, duplicados,filename, insertados):
    if not existe(register, cur):
        save_register_valid(register, cur)
        cur.execute("SELECT id_raw FROM recaudaciones_raw ORDER BY id_raw DESC limit 1")
        id_rec = cur.fetchall()
        fecha_raw = register[14]
        fecha = dar_formato_fecha(fecha_raw)
        save_recaudaciones_normalizada(fecha, id_rec[0], cur)
        insertados.append({'registro': str(register)})
        return 1
    else:
        duplicados.append({'registro': str(register)})
        return 0


# Funcion que inserta registros en la tabla recaudaciones_raw
def save_register_valid(register, cur):
    query = "INSERT INTO recaudaciones_raw(moneda, dependencia, concep, concep_a, concep_b, numero, codigo, nombre, importe, carnet, autoseguro, ave, devol_tran, observacion, fecha) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    cur.execute(query, register)

# Funcion que registra la fecha de un registro de la tabla recaudaciones segun su id
def save_recaudaciones_normalizada(fecha, id_rec, cur):
    query = "UPDATE recaudaciones SET fecha=%s WHERE id_rec=%s"
    update = (fecha, id_rec)
    cur.execute(query, update)

# Funcion que guarda el registro de carga
def save_data_for_auditoria(filename, cur):
    global name_of_pc, ip
    query = "INSERT INTO registro_carga(nombre_equipo, ip, ruta) VALUES(%s, %s, %s)"
    update = (name_of_pc, ip, filename)
    cur.execute(query, update)

# Funcion que validad si un registro existe o no en la base de datos
def existe(register, cur):
    query = "SELECT count(*) FROM recaudaciones_raw where moneda=%s AND dependencia=%s AND concep=%s AND concep_a=%s AND concep_b=%s AND numero=%s AND codigo=%s AND nombre=%s AND importe=%s AND fecha=%s;"
    data = (str(register[0]), str(register[1]), str(register[2]), str(register[3]), str(register[4]),
             str(register[5]), str(register[6]), str(register[7]), register[8], str(register[14]))
    cur.execute(query, data)
    flag = cur.fetchall()
    if int(flag[0][0]) == 0:
        return False
    return True


def save_bad_files(self):
    return True

# Funcion que sirve para guardar los registro fallidos
def save_file_upload_error(filename, error):
    try:
        conn = connect_database()
        cur = conn.cursor()
        query = "INSERT INTO recaudaciones_fallidas(nombre_archivo, descripcion_error) VALUES (%s, %s)"
        data = (filename, error)
        cur.execute(query, data)
        conn.commit()
        conn.close()
    except:
        print("I am unable to connect to the database.")

# Funcion donde se definen los formatos del excel
# Actualmente existen "2" formatos
def set_formato_excel(formato):
    if formato == 1:
        return formato_one
    if formato == 2:
        return formato_two
        return 0

# funcion que cambia el formato de la fecha de un registro
def dar_formato_fecha(fecha_raw):
    return fecha_raw[:4] + '-' + fecha_raw[4:6] + '-' + fecha_raw[6:]

def cabecera_a_texto(cabecera):
    texto = cabecera
    if(cabecera == "'_1'"):
        texto = "'COD.'"
    if(cabecera == "'_13'"):
        texto = "'DEVOL/TRANSF.'"
    return texto

if __name__ == '__main__':
    app.run(host="0.0.0.0")
