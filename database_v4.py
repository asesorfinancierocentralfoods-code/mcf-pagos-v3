
import sqlite3, pandas as pd
from pathlib import Path
from datetime import datetime
import hashlib, os, shutil

DB_PATH = Path(__file__).parent.parent / "data" / "pagos.db"
EVIDENCIAS_PATH = Path(__file__).parent.parent / "data" / "evidencias"
DB_PATH.parent.mkdir(exist_ok=True)
EVIDENCIAS_PATH.mkdir(parents=True, exist_ok=True)

def hash_password(pwd): return hashlib.sha256(pwd.encode()).hexdigest()
def get_connection():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS facturas (
        uuid TEXT PRIMARY KEY, estatus_sat TEXT, tipo TEXT, serie TEXT, folio TEXT,
        emision DATE, timbrado DATE, emisor_rfc TEXT, emisor_nombre TEXT, emisor_regimen TEXT,
        receptor_rfc TEXT, conceptos_descripcion TEXT, subtotal REAL, iva REAL, total REAL,
        moneda TEXT, forma_pago TEXT, forma_pago_desc TEXT, metodo_pago TEXT,
        created_at TIMESTAMP, updated_at TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS autorizaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL,
        importe_factura REAL, importe_autorizado REAL, saldo_pendiente REAL,
        fecha_programada DATE, semana_pago INTEGER, anio_pago INTEGER,
        estatus TEXT CHECK(estatus IN ('Pendiente','Recibido','Validado','Programado','Autorizado','Pagado','Rechazado','Parcial')),
        notas TEXT, usuario_autorizo TEXT, fecha_autorizacion TIMESTAMP, fecha_actualizacion TIMESTAMP,
        FOREIGN KEY (uuid) REFERENCES facturas(uuid))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS evidencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL,
        nombre_archivo TEXT, tipo_archivo TEXT, ruta_archivo TEXT, tamano_kb REAL,
        subido_por TEXT, rfc_proveedor TEXT, rol_subida TEXT, fecha_subida TIMESTAMP,
        validado INTEGER DEFAULT 0, validado_por TEXT, fecha_validacion TIMESTAMP,
        estatus_validacion TEXT DEFAULT 'Pendiente', notas_validacion TEXT,
        checklist_recibido INTEGER DEFAULT 0, checklist_calidad INTEGER DEFAULT 0, checklist_firma INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, rfc TEXT UNIQUE, email TEXT, telefono_whatsapp TEXT,
        rol TEXT, password_hash TEXT, activo INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS notificaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, uuid TEXT, titulo TEXT, mensaje TEXT,
        destinatario_rfc TEXT, destinatario_rol TEXT, destinatario_email TEXT, canal TEXT,
        enviado INTEGER DEFAULT 0, leido INTEGER DEFAULT 0, fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP, fecha_envio TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pagos_parciales (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL, importe_pagado REAL,
        fecha_pago DATE, forma_pago TEXT, referencia TEXT, usuario_registro TEXT, notas TEXT,
        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    cur.execute("SELECT COUNT(*) as c FROM usuarios")
    if cur.fetchone()['c']==0:
        defaults = [
            ("COSTCO DE MEXICO","CME910715UB9","costco@proveedor.com","+525500000001","Proveedor",hash_password("costco123")),
            ("SILVERIO ORTIZ AGUILA","OIAS650501JY3","silverio@proveedor.com","+525500000002","Proveedor",hash_password("proveedor123")),
            ("DISTRIBUIDORA AGRICOLA","DAQ123456789","agricola@proveedor.com","+525500000003","Proveedor",hash_password("proveedor123")),
            ("Ana CxP","CXP001","cxp@mercadocentral.com","+525500000010","CuentasPorPagar",hash_password("cxp123")),
            ("Fernando Tesoreria","TES001","tesoreria@mercadocentral.com","+525500000020","Tesoreria",hash_password("teso123")),
            ("Admin MCF","ADMIN001","admin@mercadocentral.com","+525500000030","Admin",hash_password("admin123")),
        ]
        for n,r,e,t,rol,ph in defaults:
            cur.execute("INSERT INTO usuarios (nombre,rfc,email,telefono_whatsapp,rol,password_hash) VALUES (?,?,?,?,?,?)",(n,r,e,t,rol,ph))
    conn.commit(); conn.close()

def verificar_login(rfc,pwd,rol_esp=None):
    conn=get_connection(); cur=conn.cursor()
    cur.execute("SELECT * FROM usuarios WHERE rfc=? AND activo=1",(rfc,))
    u=cur.fetchone(); conn.close()
    if not u: return None
    if u['password_hash']!=hash_password(pwd): return None
    if rol_esp and u['rol']!=rol_esp and u['rol']!='Admin': return None
    return dict(u)

def upsert_facturas(df):
    conn=get_connection(); cur=conn.cursor(); ins=upd=0
    for _,row in df.iterrows():
        uuid=row['uuid']
        cur.execute("SELECT uuid FROM facturas WHERE uuid=?",(uuid,))
        exists=cur.fetchone()
        if exists:
            cur.execute("UPDATE facturas SET estatus_sat=?,tipo=?,serie=?,folio=?,emision=?,timbrado=?,emisor_rfc=?,emisor_nombre=?,emisor_regimen=?,receptor_rfc=?,conceptos_descripcion=?,subtotal=?,iva=?,total=?,moneda=?,forma_pago=?,forma_pago_desc=?,metodo_pago=?,updated_at=? WHERE uuid=?",
                        (row.get('estatus_sat'),row.get('tipo'),row.get('serie'),row.get('folio'),str(row.get('emision')),str(row.get('timbrado')),row.get('emisor_rfc'),row.get('emisor_nombre'),row.get('emisor_regimen'),row.get('receptor_rfc'),row.get('conceptos_descripcion'),float(row.get('subtotal',0)),float(row.get('iva',0)),float(row.get('total',0)),row.get('moneda'),str(row.get('forma_pago','')),row.get('forma_pago_desc'),row.get('metodo_pago'),datetime.now(),uuid))
            upd+=1
        else:
            cur.execute("INSERT INTO facturas (uuid,estatus_sat,tipo,serie,folio,emision,timbrado,emisor_rfc,emisor_nombre,emisor_regimen,receptor_rfc,conceptos_descripcion,subtotal,iva,total,moneda,forma_pago,forma_pago_desc,metodo_pago,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (uuid,row.get('estatus_sat'),row.get('tipo'),row.get('serie'),row.get('folio'),str(row.get('emision')),str(row.get('timbrado')),row.get('emisor_rfc'),row.get('emisor_nombre'),row.get('emisor_regimen'),row.get('receptor_rfc'),row.get('conceptos_descripcion'),float(row.get('subtotal',0)),float(row.get('iva',0)),float(row.get('total',0)),row.get('moneda'),str(row.get('forma_pago','')),row.get('forma_pago_desc'),row.get('metodo_pago'),datetime.now(),datetime.now()))
            ins+=1
            cur.execute("SELECT COUNT(*) as c FROM autorizaciones WHERE uuid=?",(uuid,))
            if cur.fetchone()['c']==0:
                cur.execute("INSERT INTO autorizaciones (uuid,importe_factura,importe_autorizado,saldo_pendiente,estatus,usuario_autorizo,fecha_autorizacion,fecha_actualizacion) VALUES (?,?,?,?,?,?,?,?)",
                            (uuid,float(row.get('total',0)),0,float(row.get('total',0)),'Pendiente','SISTEMA',datetime.now(),datetime.now()))
    conn.commit(); conn.close(); return ins,upd

def guardar_evidencias_multiples(uuid, archivos, subido_por, rfc_proveedor, rol="Proveedor"):
    """NUEVO: Permite varios documentos a la vez"""
    ids=[]
    for archivo in archivos:
        conn=get_connection(); cur=conn.cursor()
        carpeta=EVIDENCIAS_PATH/uuid; carpeta.mkdir(parents=True, exist_ok=True)
        nombre=archivo.name if hasattr(archivo,'name') else f"evidencia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        ruta=carpeta/nombre
        if hasattr(archivo,'getbuffer'):
            with open(ruta,"wb") as f: f.write(archivo.getbuffer())
            tam=ruta.stat().st_size/1024; tipo=archivo.type
        else:
            shutil.copy(archivo,ruta); tam=ruta.stat().st_size/1024; tipo="octet-stream"
        cur.execute("INSERT INTO evidencias (uuid,nombre_archivo,tipo_archivo,ruta_archivo,tamano_kb,subido_por,rfc_proveedor,rol_subida,fecha_subida,estatus_validacion) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (uuid,nombre,tipo,str(ruta),tam,subido_por,rfc_proveedor,rol,datetime.now(),'Pendiente'))
        eid=cur.lastrowid; ids.append(eid)
        cur.execute("SELECT emisor_nombre FROM facturas WHERE uuid=?",(uuid,))
        prov=cur.fetchone(); proveedor=prov['emisor_nombre'] if prov else ''
        cur.execute("INSERT INTO audit_log (uuid,proveedor,accion,campo_modificado,valor_nuevo,usuario,rol,notas,timestamp) VALUES (?,?,?,?,?,?,?,?,?)",
                    (uuid,proveedor,'EVIDENCIA_SUBIDA','evidencia',nombre,subido_por,rol,f"{nombre} ({tam:.1f}KB)",datetime.now()))
        conn.commit(); conn.close()
    # Actualizar estatus a Recibido si es primera vez
    conn=get_connection(); cur=conn.cursor()
    cur.execute("UPDATE autorizaciones SET estatus='Recibido',fecha_actualizacion=? WHERE uuid=? AND estatus='Pendiente'",(datetime.now(),uuid))
    conn.commit(); conn.close()
    return ids

# Compatibilidad con version anterior (un archivo)
def guardar_evidencia(uuid,archivo,subido_por,rfc_proveedor,rol="Proveedor"):
    return guardar_evidencias_multiples(uuid,[archivo],subido_por,rfc_proveedor,rol)[0]

def get_evidencias(uuid=None, rfc=None, estatus=None):
    conn=get_connection()
    q="SELECT * FROM evidencias WHERE 1=1"; p=[]
    if uuid: q+=" AND uuid=?"; p.append(uuid)
    if rfc: q+=" AND rfc_proveedor=?"; p.append(rfc)
    if estatus: q+=" AND estatus_validacion=?"; p.append(estatus)
    q+=" ORDER BY fecha_subida DESC"
    df=pd.read_sql_query(q,conn,params=p); conn.close(); return df

def validar_evidencia(eid, validado_por, aprobado=True, notas="", checklist=None):
    conn=get_connection(); cur=conn.cursor()
    est='Aprobada' if aprobado else 'Rechazada'; checklist=checklist or {}
    cur.execute("UPDATE evidencias SET validado=?,validado_por=?,fecha_validacion=?,estatus_validacion=?,notas_validacion=?,checklist_recibido=?,checklist_calidad=?,checklist_firma=? WHERE id=?",
                (1 if aprobado else 0,validado_por,datetime.now(),est,notas,checklist.get('recibido',0),checklist.get('calidad',0),checklist.get('firma',0),eid))
    cur.execute("SELECT uuid,rfc_proveedor,nombre_archivo FROM evidencias WHERE id=?",(eid,)); row=cur.fetchone()
    if row and aprobado:
        cur.execute("UPDATE autorizaciones SET estatus='Validado',fecha_actualizacion=? WHERE uuid=? AND estatus IN ('Recibido','Pendiente')",(datetime.now(),row['uuid']))
    conn.commit(); conn.close()

def get_facturas_con_saldo(rfc=None):
    conn=get_connection()
    q="""SELECT f.uuid,f.estatus_sat,f.serie,f.folio,f.emision,f.emisor_rfc,f.emisor_nombre,f.conceptos_descripcion,
    f.subtotal,f.iva,f.total as total_factura,f.moneda,f.forma_pago_desc,
    COALESCE(SUM(CASE WHEN a.estatus IN ('Validado','Programado','Autorizado','Pagado','Parcial') THEN a.importe_autorizado ELSE 0 END),0) as total_autorizado,
    f.total - COALESCE(SUM(CASE WHEN a.estatus IN ('Validado','Programado','Autorizado','Pagado','Parcial') THEN a.importe_autorizado ELSE 0 END),0) as saldo_pendiente,
    MAX(a.fecha_programada) as ultima_fecha, MAX(a.estatus) as ultimo_estatus,
    COUNT(DISTINCT e.id) as num_evidencias,
    SUM(CASE WHEN e.estatus_validacion='Aprobada' THEN 1 ELSE 0 END) as evidencias_aprobadas,
    SUM(CASE WHEN e.estatus_validacion='Pendiente' THEN 1 ELSE 0 END) as evidencias_pendientes
    FROM facturas f LEFT JOIN autorizaciones a ON f.uuid=a.uuid LEFT JOIN evidencias e ON f.uuid=e.uuid WHERE f.estatus_sat='Vigente'"""
    p=[]
    if rfc: q+=" AND f.emisor_rfc=?"; p.append(rfc)
    q+=" GROUP BY f.uuid"
    df=pd.read_sql_query(q,conn,params=p); conn.close()
    if not df.empty: df['emision']=pd.to_datetime(df['emision'], errors='coerce')
    return df

def autorizar_pago_parcial(uuid, importe, fecha_prog, notas, usuario, total_factura):
    """NUEVO: Autorizacion parcial que permite varios pagos por factura"""
    conn=get_connection(); cur=conn.cursor(); now=datetime.now()
    try:
        dt=pd.to_datetime(fecha_prog); semana=int(dt.isocalendar().week); anio=int(dt.isocalendar().year)
    except: semana=None; anio=None
    cur.execute("SELECT f.total - COALESCE(SUM(CASE WHEN a.estatus IN ('Validado','Programado','Autorizado','Pagado','Parcial') THEN a.importe_autorizado ELSE 0 END),0) as saldo FROM facturas f LEFT JOIN autorizaciones a ON f.uuid=a.uuid WHERE f.uuid=? GROUP BY f.uuid",(uuid,))
    row=cur.fetchone(); saldo_prev=row['saldo'] if row else total_factura
    if importe > saldo_prev+0.01:
        conn.close(); return False, f"Importe {importe} excede saldo {saldo_prev}"
    nuevo_saldo=saldo_prev-importe
    estatus='Parcial' if nuevo_saldo>1 else 'Programado'
    cur.execute("INSERT INTO autorizaciones (uuid,importe_factura,importe_autorizado,saldo_pendiente,fecha_programada,semana_pago,anio_pago,estatus,notas,usuario_autorizo,fecha_autorizacion,fecha_actualizacion) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (uuid,total_factura,importe,nuevo_saldo,str(fecha_prog),semana,anio,estatus,notas,usuario,now,now))
    # Guardar tambien en pagos_parciales para historial
    cur.execute("INSERT INTO pagos_parciales (uuid,importe_pagado,fecha_pago,usuario_registro,notas) VALUES (?,?,?,?,?)",
                (uuid,importe,str(fecha_prog),usuario,notas))
    conn.commit(); conn.close(); return True, "OK"

# Compatibilidad
def get_facturas_with_saldo_y_evidencia(rfc_proveedor=None, estatus_filtro=None):
    return get_facturas_con_saldo(rfc=rfc_proveedor)
def get_facturas_with_saldo(estatus_filtro=None): return get_facturas_con_saldo()
def autorizar_pagos(lista, usuario="Tesoreria", rol="Tesoreria"):
    for item in lista:
        autorizar_pago_parcial(item['uuid'], float(item['importe_autorizado']), item['fecha_programada'], item.get('notas',''), usuario, float(item.get('total_factura',0)))
def get_historial_autorizaciones():
    conn=get_connection(); df=pd.read_sql_query("SELECT a.*,f.emisor_nombre as proveedor,f.emisor_rfc FROM autorizaciones a JOIN facturas f ON a.uuid=f.uuid ORDER BY a.fecha_autorizacion DESC",conn); conn.close(); return df
def get_audit_trail():
    conn=get_connection(); df=pd.read_sql_query("SELECT * FROM audit_log ORDER BY timestamp DESC",conn); conn.close(); return df
def get_notificaciones(rfc=None,rol=None,solo_no_leidas=False):
    return pd.DataFrame()
def crear_notificacion(*args,**kwargs): pass
def marcar_como_pagado(uuids,usuario="Tesoreria"):
    conn=get_connection(); cur=conn.cursor(); now=datetime.now()
    for uuid in uuids: cur.execute("UPDATE autorizaciones SET estatus='Pagado',fecha_actualizacion=? WHERE uuid=? AND estatus IN ('Programado','Parcial')",(now,uuid))
    conn.commit(); conn.close()
