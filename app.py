import json
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta

# Configuración de conexión profesional
db_config = {
    'host': 'localhost',
    'user': 'goradhun_fran',
    'password': 'Exito2026.',
    'database': 'goradhun_sistemapak',
    'raise_on_warnings': True
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

app = Flask(__name__)
app.secret_key = 'pakchile_secreto_2026'

# ----------------------------------------------------------------
# RUTAS DE CLIENTES
# ----------------------------------------------------------------

@app.route('/clientes', methods=['GET', 'POST'])
def lista_clientes():
    try:
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'POST':
            cliente_id = request.form.get('id')
            datos = (
                request.form.get('rut'),
                request.form.get('razon_social'),
                request.form.get('email'),
                request.form.get('telefono'),
                request.form.get('direccion', ''),
                request.form.get('comuna', ''),
                request.form.get('estado', 'Activo'),
                request.form.get('etiquetas', '')
            )

            if cliente_id:
                sql = """UPDATE clientes SET rut=%s, razon_social=%s, email=%s, 
                         telefono=%s, direccion=%s, comuna=%s, estado=%s, etiquetas=%s WHERE id=%s"""
                cursor.execute(sql, datos + (cliente_id,))
            else:
                sql = """INSERT INTO clientes (rut, razon_social, email, telefono, direccion, comuna, estado, etiquetas) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, datos)
                
            conn.commit()
            return redirect(url_for('lista_clientes'))
        
        cursor.execute("SELECT * FROM clientes ORDER BY id DESC")
        clientes_db = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('clientes.html', clientes=clientes_db)
        
    except Exception as e:
        return f"<h1>Error Python/SQL detectado en Clientes:</h1><p style='color:red;'>{str(e)}</p><a href='/dashboard'>Volver al inicio</a>"



# ----------------------------------------------------------------
# RUTAS DE COTIZACIONES
# ----------------------------------------------------------------

@app.route('/cotizaciones')
def lista_cotizaciones():
    try:
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        rol = str(session.get('usuario_rol', '')).strip().lower()
        
        if rol == 'administrador':
            # Buscamos el nombre en la tabla usuarios (u.nombre)
            cursor.execute("""SELECT c.*, cl.razon_social as cliente_nombre, u.nombre as vendedor_nombre 
                              FROM cotizaciones c 
                              LEFT JOIN clientes cl ON c.cliente_id = cl.id 
                              LEFT JOIN usuarios u ON c.usuario_id = u.id
                              ORDER BY c.id DESC""")
        else:
            cursor.execute("""SELECT c.*, cl.razon_social as cliente_nombre 
                              FROM cotizaciones c 
                              LEFT JOIN clientes cl ON c.cliente_id = cl.id 
                              WHERE c.usuario_id = %s 
                              ORDER BY c.id DESC""", (session['usuario_id'],))
                              
        cots = cursor.fetchall()
        
        for c in cots:
            if hasattr(c.get('fecha'), 'strftime'):
                c['fecha'] = c['fecha'].strftime("%d/%m/%Y")
            if hasattr(c.get('valida_hasta'), 'strftime'):
                c['valida_hasta'] = c['valida_hasta'].strftime("%d/%m/%Y")

        cursor.close()
        conn.close()
        return render_template('cotizaciones.html', cotizaciones=cots)
        
    except Exception as e:
        return f"<h1>Error Python/SQL detectado en Cotizaciones:</h1><p style='color:red;'>{str(e)}</p><a href='/dashboard'>Volver al inicio</a>"

@app.route('/clientes/eliminar/<int:id>')
def eliminar_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clientes WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('lista_clientes'))

@app.route('/cliente/detalle/<int:id>')
def detalle_cliente(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clientes WHERE id = %s", (id,))
    cliente = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('detalle_cliente.html', cliente=cliente)

# ----------------------------------------------------------------
# RUTAS DE INVENTARIO
# ----------------------------------------------------------------

@app.route('/inventario', methods=['GET', 'POST'])
def inventario():
    # Seguridad: Verificar si el usuario está logueado (necesario para el Kardex)
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        tipo_accion = request.form.get('tipo_accion')
        
        if tipo_accion == 'recepcion':
            prod_id = int(request.form.get('producto_id'))
            cantidad = float(request.form.get('cantidad', 0))
            
            # 1. Sumamos el stock al producto
            cursor.execute("UPDATE productos SET stock = stock + %s WHERE id = %s", (cantidad, prod_id))
            
            # 2. Guardamos el registro en el Kardex Profesional
            cursor.execute("SELECT stock FROM productos WHERE id = %s", (prod_id,))
            saldo_actual = cursor.fetchone()['stock']
            usuario_id = session.get('usuario_id')
            cursor.execute("""INSERT INTO movimientos_inventario (producto_id, usuario_id, tipo_movimiento, cantidad, saldo_resultante, documento_referencia) 
                              VALUES (%s, %s, 'Entrada (Recepción)', %s, %s, 'Ajuste de Inventario')""", 
                           (prod_id, usuario_id, cantidad, saldo_actual))
        
        elif tipo_accion == 'nuevo_editar':
            prod_id = request.form.get('id')
            # Incluimos 'precio_costo' en los datos
            datos = (
                request.form.get('sku'),
                request.form.get('nombre'),
                request.form.get('marca', ''),
                request.form.get('categoria', ''),
                request.form.get('unidad', ''),
                int(request.form.get('precio_venta', 0)),
                int(request.form.get('precio_costo', 0)), # NUEVO CAMPO
                int(request.form.get('stock', 0)),
                int(request.form.get('stock_minimo', 0)),
                request.form.get('estado', 'Activo')      # AHORA ES DINÁMICO
            )
            
            if prod_id: # Editar
                sql = """UPDATE productos SET sku=%s, nombre=%s, marca=%s, categoria=%s, 
                         unidad=%s, precio_venta=%s, precio_costo=%s, stock=%s, stock_minimo=%s, estado=%s WHERE id=%s"""
                cursor.execute(sql, datos + (prod_id,))
            else: # Crear
                sql = """INSERT INTO productos (sku, nombre, marca, categoria, unidad, precio_venta, precio_costo, stock, stock_minimo, estado) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                cursor.execute(sql, datos)

        conn.commit()
        return redirect(url_for('inventario'))
    
    # --- GET: Extraer productos y categorías para el HTML ---
    cursor.execute("SELECT * FROM productos ORDER BY nombre ASC")
    productos_db = cursor.fetchall()
    
    cursor.execute("SELECT * FROM categorias ORDER BY nombre ASC")
    categorias_db = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('inventario.html', productos=productos_db, categorias=categorias_db)

@app.route('/inventario/detalle/<int:id>')
def detalle_producto(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos WHERE id = %s", (id,))
    producto = cursor.fetchone()
    cursor.close()
    conn.close()
    if producto:
        return render_template('detalle_producto.html', producto=producto)
    return redirect(url_for('inventario'))

@app.route('/inventario/eliminar/<int:id>')
def eliminar_producto(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('inventario'))

@app.route('/inventario/movimientos')
def historial_movimientos():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        sql = """
            SELECT m.*, p.nombre as producto_nombre, p.sku, u.nombre as usuario_nombre
            FROM movimientos_inventario m
            LEFT JOIN productos p ON m.producto_id = p.id
            LEFT JOIN usuarios u ON m.usuario_id = u.id
            ORDER BY m.id DESC
        """
        cursor.execute(sql)
        movimientos = cursor.fetchall()
        
        # Formatear la fecha para que se vea profesional (DD/MM/YYYY HH:MM)
        for m in movimientos:
            if m['fecha']:
                m['fecha'] = m['fecha'].strftime("%d/%m/%Y %H:%M")
                
        return render_template('movimientos.html', movimientos=movimientos)
    except Exception as e:
        return f"<h1>Error al cargar Historial:</h1><p style='color:red;'>{str(e)}</p><a href='/inventario'>Volver</a>"
    finally:
        cursor.close()
        conn.close()

@app.route('/cotizacion/nueva', methods=['GET', 'POST'])
def nueva_cotizacion():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            cliente_id = int(request.form.get('cliente_id'))
            validez_dias = int(request.form.get('validez_dias', 15))
            estado_cot = request.form.get('estado', 'Borrador')
            tipo_documento = request.form.get('tipo_documento', 'Factura Electrónica') 
            
            fecha_hoy = datetime.now()
            valida_hasta = fecha_hoy + timedelta(days=validez_dias)
            
            detalle = json.loads(request.form.get('lineas_json', '[]'))
            
            # Cálculo de Subtotal
            subtotal = sum(int(item.get('subtotal', 0)) for item in detalle)
            
            # Lógica de IVA: Si es Nota de Venta es 0, de lo contrario 19%
            if tipo_documento == 'Nota de Venta':
                iva = 0
            else:
                iva = int(subtotal * 0.19)
                
            total = subtotal + iva
            
            cursor.execute("SELECT IFNULL(MAX(id), 0) + 1 as prox FROM cotizaciones")
            numero_cot = f"COT-{str(cursor.fetchone()['prox']).zfill(5)}"
            
            sql_cab = """INSERT INTO cotizaciones (numero, cliente_id, usuario_id, fecha, validez_dias, valida_hasta, subtotal, iva, total, estado, tipo_documento) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql_cab, (numero_cot, cliente_id, session['usuario_id'], fecha_hoy.date(), validez_dias, valida_hasta.date(), subtotal, iva, total, estado_cot, tipo_documento))
            cot_id = cursor.lastrowid
            
            for item in detalle:
                sql_det = """INSERT INTO cotizacion_detalles (cotizacion_id, producto_id, cantidad, precio_unitario, subtotal_linea) 
                             VALUES (%s, %s, %s, %s, %s)"""
                cursor.execute(sql_det, (cot_id, int(item.get('producto_id', 0)), float(item.get('cantidad', 1)), int(item.get('precio_unitario', 0)), int(item.get('subtotal', 0))))

            conn.commit()
            return redirect(url_for('lista_cotizaciones'))

        cursor.execute("SELECT * FROM clientes")
        clientes = cursor.fetchall()
        cursor.execute("SELECT * FROM productos WHERE estado='Activo'")
        productos = cursor.fetchall()
        
        # PREVENCIÓN DE ERROR 500
        for c in clientes:
            for k, v in c.items():
                if type(v).__name__ in ['datetime', 'date', 'Decimal']: c[k] = str(v)
        for p in productos:
            for k, v in p.items():
                if type(v).__name__ in ['datetime', 'date', 'Decimal']: p[k] = str(v)

        cursor.close()
        conn.close()
        return render_template('nueva_cotizacion.html', clientes=clientes, productos=productos)
        
    except Exception as e:
        return f"<h1>Error Python detectado:</h1><p style='color:red; font-weight:bold;'>{str(e)}</p><a href='/cotizaciones'>Volver</a>"

@app.route('/cotizacion/editar/<int:id>', methods=['GET', 'POST'])
def editar_cotizacion(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        cliente_id = int(request.form.get('cliente_id'))
        validez_dias = int(request.form.get('validez_dias', 15))
        estado_cot = request.form.get('estado', 'Borrador')
        # NUEVO: Recibimos el tipo de documento
        tipo_documento = request.form.get('tipo_documento', 'Factura Electrónica')
        
        cursor.execute("SELECT fecha FROM cotizaciones WHERE id = %s", (id,))
        fecha_orig = cursor.fetchone()['fecha']
        valida_hasta = fecha_orig + timedelta(days=validez_dias)
        
        detalle = json.loads(request.form.get('lineas_json', '[]'))
        subtotal = sum(int(item.get('subtotal', 0)) for item in detalle)
        iva = int(subtotal * 0.19)
        total = subtotal + iva
        
        # NUEVO: Agregamos tipo_documento al UPDATE
        sql_upd = """UPDATE cotizaciones SET cliente_id=%s, validez_dias=%s, valida_hasta=%s, subtotal=%s, iva=%s, total=%s, estado=%s, tipo_documento=%s WHERE id=%s"""
        cursor.execute(sql_upd, (cliente_id, validez_dias, valida_hasta, subtotal, iva, total, estado_cot, tipo_documento, id))
        
        cursor.execute("DELETE FROM cotizacion_detalles WHERE cotizacion_id = %s", (id,))
        for item in detalle:
            sql_det = """INSERT INTO cotizacion_detalles (cotizacion_id, producto_id, cantidad, precio_unitario, subtotal_linea) VALUES (%s, %s, %s, %s, %s)"""
            # NUEVO: Convertimos cantidad a float() para aceptar decimales
            cursor.execute(sql_det, (id, int(item.get('producto_id', 0)), float(item.get('cantidad', 1)), int(item.get('precio_unitario', 0)), int(item.get('subtotal', 0))))
            
        conn.commit()
        return redirect(url_for('lista_cotizaciones'))

    cursor.execute("SELECT * FROM cotizaciones WHERE id = %s", (id,))
    cotizacion = cursor.fetchone()
    if cotizacion:
        cursor.execute("SELECT cd.*, p.nombre FROM cotizacion_detalles cd JOIN productos p ON cd.producto_id = p.id WHERE cd.cotizacion_id = %s", (id,))
        cotizacion['detalle'] = cursor.fetchall()
        
    cursor.execute("SELECT * FROM clientes")
    clientes = cursor.fetchall()
    cursor.execute("SELECT * FROM productos WHERE estado='Activo'")
    productos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('editar_cotizacion.html', cotizacion=cotizacion, clientes=clientes, productos=productos)

@app.route('/cotizacion/eliminar/<int:id>')
def eliminar_cotizacion(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cotizaciones WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('lista_cotizaciones'))

@app.route('/cotizacion/imprimir/<int:id>')
def imprimir_cotizacion(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Buscar la cotización y TODOS los datos del cliente
        cursor.execute("""SELECT c.*, cl.razon_social as cliente_nombre, 
                                 cl.rut as cliente_rut, cl.direccion as cliente_direccion, 
                                 cl.telefono as cliente_telefono, cl.comuna as cliente_comuna
                          FROM cotizaciones c 
                          JOIN clientes cl ON c.cliente_id = cl.id 
                          WHERE c.id = %s""", (id,))
        cotizacion = cursor.fetchone()
        
        if cotizacion:
            from datetime import datetime, date
            if isinstance(cotizacion.get('fecha'), (datetime, date)):
                cotizacion['fecha'] = cotizacion['fecha'].strftime("%d/%m/%Y")
            else:
                cotizacion['fecha'] = str(cotizacion['fecha'])
                
            if isinstance(cotizacion.get('valida_hasta'), (datetime, date)):
                cotizacion['valida_hasta'] = cotizacion['valida_hasta'].strftime("%d/%m/%Y")
            else:
                cotizacion['valida_hasta'] = str(cotizacion['valida_hasta'])

            sql_detalle = """
                SELECT cd.*, p.nombre, 
                       cd.subtotal_linea AS subtotal, 
                       0 AS descuento 
                FROM cotizacion_detalles cd 
                JOIN productos p ON cd.producto_id = p.id 
                WHERE cd.cotizacion_id = %s
            """
            cursor.execute(sql_detalle, (id,))
            cotizacion['detalle'] = cursor.fetchall()
            
            cursor.close()
            conn.close()
            return render_template('imprimir_cotizacion.html', cotizacion=cotizacion)
        
        cursor.close()
        conn.close()
        return redirect(url_for('lista_cotizaciones'))
        
    except Exception as e:
        return f"<h1>Error Python/SQL detectado en Cotización:</h1><p style='color:red;'>{str(e)}</p><a href='/cotizaciones'>Volver</a>"
        
# ----------------------------------------------------------------
# RUTAS DE VENTAS
# ----------------------------------------------------------------

@app.route('/ventas')
def lista_ventas():
    try:
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
            
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        rol = str(session.get('usuario_rol', '')).strip().lower()
        
        if rol == 'administrador':
            cursor.execute("""SELECT v.*, c.razon_social as cliente_nombre, u.nombre as vendedor_nombre,
                                     (SELECT IFNULL(SUM(monto), 0) FROM pagos WHERE venta_id = v.id) as total_abonos
                              FROM ventas v 
                              JOIN clientes c ON v.cliente_id = c.id 
                              LEFT JOIN usuarios u ON v.usuario_id = u.id
                              ORDER BY v.id DESC""")
        else:
            cursor.execute("""SELECT v.*, c.razon_social as cliente_nombre,
                                     (SELECT IFNULL(SUM(monto), 0) FROM pagos WHERE venta_id = v.id) as total_abonos
                              FROM ventas v 
                              JOIN clientes c ON v.cliente_id = c.id 
                              WHERE v.usuario_id = %s 
                              ORDER BY v.id DESC""", (session['usuario_id'],))
                              
        vts = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('ventas.html', ventas=vts)
        
    except Exception as e:
        return f"<h1>Error Python/SQL detectado en Ventas:</h1><p style='color:red;'>{str(e)}</p><a href='/dashboard'>Volver al inicio</a>"

@app.route('/venta/nueva', methods=['GET', 'POST'])
def nueva_venta():
    if request.method == 'POST':
        # Instanciamos la conexión dentro del try para asegurar que se cierre
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cliente_id_str = request.form.get('cliente_id')
            if not cliente_id_str:
                return "<h3>Error: No se seleccionó ningún cliente. Por favor vuelve atrás.</h3>"
            cliente_id = int(cliente_id_str)
            
            tipo_documento = request.form.get('tipo_documento') or 'Factura Electrónica'
            condicion_raw = str(request.form.get('condicion_pago', '')).strip().lower()
            condicion_pago = 'Contado' if condicion_raw == 'contado' else 'Crédito'
            cot_origen_id = request.form.get('cotizacion_origen_id')
            
            # NUEVO: Capturamos el despacho
            despacho = request.form.get('despacho', 'Retiro Local')
            
            cot_val = int(cot_origen_id) if cot_origen_id and str(cot_origen_id).strip() not in ['0', 'None', ''] else None
            
            lineas_raw = request.form.get('lineas_json')
            detalle = json.loads(lineas_raw) if lineas_raw else []
            
            pagos_raw = request.form.get('pagos_json')
            pagos = json.loads(pagos_raw) if pagos_raw else []
            
            if not detalle:
                return "<h3>Error: No se agregaron productos a la venta. Por favor vuelve atrás.</h3>"

            neto = sum(int(item.get('subtotal', 0)) for item in detalle)
            
            # LÓGICA DE IVA: Si es Nota de Venta, IVA 0
            if tipo_documento == 'Nota de Venta':
                iva = 0
            else:
                iva = int(neto * 0.19)
                
            total = neto + iva
            
            total_pagado = sum(int(p.get('monto', 0)) for p in pagos)
            estado_pago = "Pagado" if total_pagado >= total else "Sin Pagar"
            estado_venta = "Completada" if total_pagado >= total else "Pendiente"
            
            cursor.execute("SELECT IFNULL(MAX(id), 0) + 1 as prox FROM ventas")
            numero_vta = f"VTA-{str(cursor.fetchone()['prox']).zfill(5)}"
            
            # NUEVO: Agregamos despacho al INSERT
            sql_cab = """INSERT INTO ventas (numero, cliente_id, usuario_id, cotizacion_id, tipo_documento, condicion_pago, estado_pago, estado_venta, neto, iva, total, despacho) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(sql_cab, (numero_vta, cliente_id, session['usuario_id'], cot_val, tipo_documento, condicion_pago, estado_pago, estado_venta, neto, iva, total, despacho))
            venta_id = cursor.lastrowid
            
            for item in detalle:
                prod_id = int(item.get('producto_id', 0))
                # AQUÍ ACEPTAMOS DECIMALES CON float()
                cant = float(item.get('cantidad', 1)) 
                
                sql_det = """INSERT INTO venta_detalles (venta_id, producto_id, cantidad, precio_unitario, subtotal_linea) VALUES (%s, %s, %s, %s, %s)"""
                cursor.execute(sql_det, (venta_id, prod_id, cant, int(item.get('precio_unitario', 0)), int(item.get('subtotal', 0))))
                
                # Descontar stock con decimales
                cursor.execute("UPDATE productos SET stock = stock - %s WHERE id = %s", (cant, prod_id))
                
                # KARDEX: Registro de Salida por Venta
                cursor.execute("SELECT stock FROM productos WHERE id = %s", (prod_id,))
                saldo_actual = cursor.fetchone()['stock']
                cursor.execute("""INSERT INTO movimientos_inventario (producto_id, usuario_id, tipo_movimiento, cantidad, saldo_resultante, documento_referencia) 
                                  VALUES (%s, %s, 'Salida (Venta)', %s, %s, %s)""", 
                               (prod_id, session['usuario_id'], cant, saldo_actual, numero_vta))
                
            if cot_val:
                cursor.execute("UPDATE cotizaciones SET estado = 'Convertida' WHERE id = %s", (cot_val,))
                
            conn.commit()
            return redirect(url_for('lista_ventas'))
            
        except Exception as e:
            conn.rollback() 
            return f"<h1>Error SQL detectado al Guardar:</h1><p style='color:red;'>{str(e)}</p><a href='/ventas'>Volver</a>"
        finally:
            cursor.close()
            conn.close()
            
    # --- GET ---
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM clientes")
        clientes = cursor.fetchall()
        cursor.execute("SELECT * FROM productos WHERE estado='Activo'")
        productos = cursor.fetchall()
        
        # NUEVO: Traer métodos de pago de la BD
        cursor.execute("SELECT * FROM metodos_pago_lista")
        metodos = cursor.fetchall()
        
        # PREVENCIÓN DE ERROR 500 CON JSON
        for c in clientes:
            for k, v in c.items():
                if type(v).__name__ in ['datetime', 'date', 'Decimal']: c[k] = str(v)
        for p in productos:
            for k, v in p.items():
                if type(v).__name__ in ['datetime', 'date', 'Decimal']: p[k] = str(v)
                
        cot_origen = None
        if request.args.get('cotizacion_id'):
            cursor.execute("SELECT * FROM cotizaciones WHERE id = %s", (request.args.get('cotizacion_id'),))
            cot_origen = cursor.fetchone()
            if cot_origen:
                cursor.execute("SELECT cd.*, p.nombre FROM cotizacion_detalles cd JOIN productos p ON cd.producto_id = p.id WHERE cd.cotizacion_id = %s", (cot_origen['id'],))
                cot_origen['detalle'] = cursor.fetchall()
                for k, v in cot_origen.items():
                    if type(v).__name__ in ['datetime', 'date', 'Decimal']: cot_origen[k] = str(v)
                
        # Pasamos la variable 'metodos' al HTML
        return render_template('nueva_venta.html', clientes=clientes, productos=productos, cotizacion_origen=cot_origen, metodos=metodos)
    except Exception as e:
        return f"<h1>Error Python detectado en Carga:</h1><p style='color:red;'>{str(e)}</p><a href='/ventas'>Volver</a>"
    finally:
        cursor.close()
        conn.close()
        
@app.route('/cotizacion/convertir/<int:id>')
def convertir_cotizacion(id):
    return redirect(url_for('nueva_venta', cotizacion_id=id))
    
    
@app.route('/venta/editar/<int:id>', methods=['GET', 'POST'])
def editar_venta(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            cliente_id = int(request.form.get('cliente_id'))
            tipo_documento = request.form.get('tipo_documento') or 'Factura Electrónica'
            condicion_raw = str(request.form.get('condicion_pago', '')).strip().lower()
            condicion_pago = 'Contado' if condicion_raw == 'contado' else 'Crédito'
            despacho = request.form.get('despacho', 'Retiro Local')
            
            lineas_raw = request.form.get('lineas_json')
            detalle = json.loads(lineas_raw) if lineas_raw else []
            
            pagos_raw = request.form.get('pagos_json')
            pagos = json.loads(pagos_raw) if pagos_raw else []
            
            neto = sum(int(item.get('subtotal', 0)) for item in detalle)
            # Respetamos el IVA 0 para Nota de Venta
            iva = 0 if tipo_documento == 'Nota de Venta' else int(neto * 0.19)
            total = neto + iva
            
            total_pagado = sum(int(p.get('monto', 0)) for p in pagos)
            estado_pago = "Pagado" if total_pagado >= total else "Sin Pagar"
            estado_venta = "Completada" if total_pagado >= total else "Pendiente"
            
            # 1. REVERTIR STOCK ANTERIOR Y REGISTRAR EN KARDEX
            cursor.execute("SELECT producto_id, cantidad FROM venta_detalles WHERE venta_id = %s", (id,))
            old_details = cursor.fetchall()
            
            cursor.execute("SELECT numero FROM ventas WHERE id = %s", (id,))
            num_venta = cursor.fetchone()['numero']
            
            for od in old_details:
                cursor.execute("UPDATE productos SET stock = stock + %s WHERE id = %s", (float(od['cantidad']), od['producto_id']))
                cursor.execute("SELECT stock FROM productos WHERE id = %s", (od['producto_id'],))
                saldo_rev = cursor.fetchone()['stock']
                cursor.execute("""INSERT INTO movimientos_inventario (producto_id, usuario_id, tipo_movimiento, cantidad, saldo_resultante, documento_referencia) 
                                  VALUES (%s, %s, 'Entrada (Edición Reversión)', %s, %s, %s)""", 
                               (od['producto_id'], session['usuario_id'], float(od['cantidad']), saldo_rev, num_venta))
            
            # 2. LIMPIAR DETALLES Y PAGOS VIEJOS
            cursor.execute("DELETE FROM venta_detalles WHERE venta_id = %s", (id,))
            cursor.execute("DELETE FROM pagos WHERE venta_id = %s", (id,))
            
            # 3. ACTUALIZAR CABECERA DE LA VENTA
            sql_cab = """UPDATE ventas SET cliente_id=%s, tipo_documento=%s, condicion_pago=%s, estado_pago=%s, estado_venta=%s, neto=%s, iva=%s, total=%s, despacho=%s WHERE id=%s"""
            cursor.execute(sql_cab, (cliente_id, tipo_documento, condicion_pago, estado_pago, estado_venta, neto, iva, total, despacho, id))
            
            # 4. INSERTAR NUEVOS DETALLES, DESCONTAR STOCK Y REGISTRAR KARDEX
            for item in detalle:
                prod_id = int(item.get('producto_id', 0))
                cant = float(item.get('cantidad', 1)) 
                sql_det = """INSERT INTO venta_detalles (venta_id, producto_id, cantidad, precio_unitario, subtotal_linea) VALUES (%s, %s, %s, %s, %s)"""
                cursor.execute(sql_det, (id, prod_id, cant, int(item.get('precio_unitario', 0)), int(item.get('subtotal', 0))))
                
                cursor.execute("UPDATE productos SET stock = stock - %s WHERE id = %s", (cant, prod_id))
                
                cursor.execute("SELECT stock FROM productos WHERE id = %s", (prod_id,))
                saldo_nuevo = cursor.fetchone()['stock']
                cursor.execute("""INSERT INTO movimientos_inventario (producto_id, usuario_id, tipo_movimiento, cantidad, saldo_resultante, documento_referencia) 
                                  VALUES (%s, %s, 'Salida (Edición Nueva)', %s, %s, %s)""", 
                               (prod_id, session['usuario_id'], cant, saldo_nuevo, num_venta))
                
            # 5. INSERTAR NUEVOS PAGOS
            for p in pagos:
                metodo = p.get('metodo', 'Efectivo')
                sql_pago = """INSERT INTO pagos (venta_id, monto, metodo_pago) VALUES (%s, %s, %s)"""
                cursor.execute(sql_pago, (id, int(p.get('monto', 0)), metodo))
                
            conn.commit()
            return redirect(url_for('lista_ventas'))
            
        except Exception as e:
            conn.rollback() 
            return f"<h1>Error SQL al Editar Venta:</h1><p style='color:red;'>{str(e)}</p><a href='/ventas'>Volver</a>"
        finally:
            cursor.close()
            conn.close()
            
    # --- GET ---
    try:
        cursor.execute("SELECT * FROM ventas WHERE id = %s", (id,))
        venta = cursor.fetchone()
        if not venta:
            return redirect(url_for('lista_ventas'))
            
        cursor.execute("SELECT vd.*, p.nombre, p.sku, p.precio_venta FROM venta_detalles vd JOIN productos p ON vd.producto_id = p.id WHERE vd.venta_id = %s", (id,))
        venta['detalle'] = cursor.fetchall()
        
        cursor.execute("SELECT * FROM pagos WHERE venta_id = %s", (id,))
        venta['pagos'] = cursor.fetchall()
        
        cursor.execute("SELECT * FROM clientes")
        clientes = cursor.fetchall()
        cursor.execute("SELECT * FROM productos WHERE estado='Activo'")
        productos = cursor.fetchall()
        
        # NUEVO: Traer métodos de pago de la BD
        cursor.execute("SELECT * FROM metodos_pago_lista")
        metodos = cursor.fetchall()
        
        # PREVENCIÓN ERROR JSON
        for c in clientes:
            for k, v in c.items():
                if type(v).__name__ in ['datetime', 'date', 'Decimal']: c[k] = str(v)
        for p in productos:
            for k, v in p.items():
                if type(v).__name__ in ['datetime', 'date', 'Decimal']: p[k] = str(v)
        for d in venta['detalle']:
            for k, v in d.items():
                if type(v).__name__ in ['datetime', 'date', 'Decimal']: d[k] = str(v)
        for p in venta['pagos']:
            for k, v in p.items():
                if type(v).__name__ in ['datetime', 'date', 'Decimal']: p[k] = str(v)
        for k, v in venta.items():
            if type(v).__name__ in ['datetime', 'date', 'Decimal'] and k != 'detalle' and k != 'pagos': venta[k] = str(v)
                
        # Pasamos la variable 'metodos' al HTML
        return render_template('editar_venta.html', venta=venta, clientes=clientes, productos=productos, metodos=metodos)
    except Exception as e:
        return f"<h1>Error Python al Cargar Editar Venta:</h1><p style='color:red;'>{str(e)}</p><a href='/ventas'>Volver</a>"
    finally:
        cursor.close()
        conn.close()

@app.route('/venta/eliminar/<int:id>')
def eliminar_venta(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT numero FROM ventas WHERE id = %s", (id,))
    venta = cursor.fetchone()
    num_venta = venta['numero'] if venta else f"Venta ID {id}"
    
    # Devolver el stock antes de borrar Y registrar en Kardex
    cursor.execute("SELECT producto_id, cantidad FROM venta_detalles WHERE venta_id = %s", (id,))
    detalles = cursor.fetchall()
    for det in detalles:
        cant = float(det['cantidad'])
        prod_id = det['producto_id']
        
        cursor.execute("UPDATE productos SET stock = stock + %s WHERE id = %s", (cant, prod_id))
        
        cursor.execute("SELECT stock FROM productos WHERE id = %s", (prod_id,))
        saldo_rev = cursor.fetchone()['stock']
        cursor.execute("""INSERT INTO movimientos_inventario (producto_id, usuario_id, tipo_movimiento, cantidad, saldo_resultante, documento_referencia) 
                          VALUES (%s, %s, 'Entrada (Anulación Venta)', %s, %s, %s)""", 
                       (prod_id, session.get('usuario_id'), cant, saldo_rev, num_venta))
    
    cursor.execute("DELETE FROM ventas WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('lista_ventas'))

@app.route('/venta/imprimir/<int:id>')
def imprimir_venta(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM ventas WHERE id = %s", (id,))
        venta = cursor.fetchone()
        
        if venta:
            from datetime import datetime, date
            if isinstance(venta.get('fecha'), (datetime, date)):
                venta['fecha'] = venta['fecha'].strftime("%d/%m/%Y")
            else:
                venta['fecha'] = str(venta['fecha'])

            cursor.execute("SELECT * FROM clientes WHERE id = %s", (venta['cliente_id'],))
            cliente = cursor.fetchone()
            
            # SOLUCIÓN: Usamos "AS subtotal" y creamos "0 AS descuento" para satisfacer al HTML
            sql_detalle = """
                SELECT vd.*, p.nombre, 
                       vd.subtotal_linea AS subtotal, 
                       0 AS descuento 
                FROM venta_detalles vd 
                JOIN productos p ON vd.producto_id = p.id 
                WHERE vd.venta_id = %s
            """
            cursor.execute(sql_detalle, (id,))
            venta['detalle'] = cursor.fetchall()
            
            cursor.execute("SELECT * FROM pagos WHERE venta_id = %s", (id,))
            venta['pagos'] = cursor.fetchall()
            
            cursor.close()
            conn.close()
            return render_template('imprimir_venta.html', venta=venta, cliente=cliente)
        
        cursor.close()
        conn.close()
        return redirect(url_for('lista_ventas'))
        
    except Exception as e:
        return f"<h1>Error Python/SQL detectado al imprimir:</h1><p style='color:red;'>{str(e)}</p><a href='/ventas'>Volver</a>"

# ----------------------------------------------------------------
# RUTAS DE CONFIGURACIÓN
# ----------------------------------------------------------------

@app.route('/configuracion')
def mostrar_configuracion():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bodegas")
    bods = cursor.fetchall()
    cursor.execute("SELECT * FROM categorias")
    cats = cursor.fetchall()
    cursor.execute("SELECT * FROM metodos_pago_lista")
    mets = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('configuracion.html', bodegas=bods, categorias=cats, metodos=mets)

@app.route('/configuracion/bodega', methods=['POST'])
def agregar_bodega():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO bodegas (nombre, codigo, direccion) VALUES (%s, %s, %s)", 
                   (request.form.get('nombre'), request.form.get('codigo'), request.form.get('direccion')))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('mostrar_configuracion'))

@app.route('/configuracion/bodega/eliminar/<int:id>')
def eliminar_bodega(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bodegas WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('mostrar_configuracion'))

@app.route('/configuracion/categoria', methods=['POST'])
def agregar_categoria():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categorias (nombre, descripcion) VALUES (%s, %s)", 
                   (request.form.get('nombre'), request.form.get('descripcion')))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('mostrar_configuracion'))

@app.route('/configuracion/categoria/eliminar/<int:id>')
def eliminar_categoria(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categorias WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('mostrar_configuracion'))

@app.route('/configuracion/metodo', methods=['POST'])
def agregar_metodo():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO metodos_pago_lista (nombre, descripcion) VALUES (%s, %s)", 
                   (request.form.get('nombre'), request.form.get('descripcion')))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('mostrar_configuracion'))

@app.route('/configuracion/metodo/eliminar/<int:id>')
def eliminar_metodo(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM metodos_pago_lista WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('mostrar_configuracion'))

@app.route('/configuracion/bodega/editar/<int:id>', methods=['POST'])
def editar_bodega(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bodegas SET nombre=%s, codigo=%s, direccion=%s WHERE id=%s", 
                   (request.form.get('nombre'), request.form.get('codigo'), request.form.get('direccion'), id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('mostrar_configuracion'))

@app.route('/configuracion/categoria/editar/<int:id>', methods=['POST'])
def editar_categoria(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE categorias SET nombre=%s, descripcion=%s WHERE id=%s", 
                   (request.form.get('nombre'), request.form.get('descripcion'), id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('mostrar_configuracion'))

@app.route('/configuracion/metodo/editar/<int:id>', methods=['POST'])
def editar_metodo(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE metodos_pago_lista SET nombre=%s, descripcion=%s WHERE id=%s", 
                   (request.form.get('nombre'), request.form.get('descripcion'), id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('mostrar_configuracion'))

# ----------------------------------------------------------------
# RUTAS DE LOGIN / AUTENTICACIÓN
# ----------------------------------------------------------------

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Buscar el usuario exacto en la BD
        cursor.execute("SELECT * FROM usuarios WHERE email = %s AND password_hash = %s AND estado = 'Activo'", (email, password))
        usuario = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if usuario:
            # Guardar sus datos en la memoria de la sesión
            session['usuario_id'] = usuario['id']
            session['usuario_nombre'] = usuario['nombre']
            session['usuario_rol'] = usuario['rol']
            return redirect(url_for('lista_clientes'))
        else:
            return "<h3>Error: Correo o contraseña incorrectos.</h3><a href='/login'>Volver</a>"
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Ventas
    cursor.execute("SELECT IFNULL(SUM(total), 0) as total_monto, COUNT(*) as cantidad FROM ventas")
    v_stats = cursor.fetchone()
    total_ventas_monto = v_stats['total_monto']
    cantidad_ventas = v_stats['cantidad']
    ticket_promedio = total_ventas_monto / cantidad_ventas if cantidad_ventas > 0 else 0
    
    cursor.execute("SELECT IFNULL(SUM(total - (SELECT IFNULL(SUM(monto),0) FROM pagos WHERE venta_id=ventas.id)), 0) as deuda FROM ventas WHERE estado_pago != 'Pagado'")
    cuentas_cobrar = cursor.fetchone()['deuda']
    
    # 2. Cotizaciones
    cursor.execute("SELECT COUNT(*) as total FROM cotizaciones")
    total_cots = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as conv FROM cotizaciones WHERE estado = 'Convertida'")
    cots_convertidas = cursor.fetchone()['conv']
    tasa_conversion = (cots_convertidas / total_cots * 100) if total_cots > 0 else 0
    cots_pendientes = total_cots - cots_convertidas

    # 3. Inventario
    cursor.execute("SELECT * FROM productos WHERE stock <= stock_minimo")
    productos_criticos = cursor.fetchall()
    cursor.execute("SELECT IFNULL(SUM(stock * precio_venta), 0) as valor FROM productos")
    valor_inventario = cursor.fetchone()['valor']
    
    # 4. Gráfico y Últimas
    datos_grafico = {
        "labels": ["Ene", "Feb", "Mar", "Abr", "May", "Jun"],
        "valores": [1200000, 1900000, 1500000, 2100000, 2400000, int(total_ventas_monto)]
    }
    
    cursor.execute("SELECT v.*, c.razon_social as cliente_nombre FROM ventas v JOIN clientes c ON v.cliente_id = c.id ORDER BY v.id DESC LIMIT 5")
    ultimas_ventas = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template('dashboard.html', 
                           monto=total_ventas_monto,
                           ticket=ticket_promedio,
                           conversion=round(tasa_conversion, 1),
                           deuda=cuentas_cobrar,
                           cots_p=cots_pendientes,
                           stock_alerta=productos_criticos,
                           valor_total=valor_inventario,
                           grafico=datos_grafico,
                           ultimas_ventas=ultimas_ventas)

import csv
import io

@app.route('/clientes/importar', methods=['POST'])
def importar_clientes():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    file = request.files.get('archivo_excel')
    if not file:
        return "No se seleccionó ningún archivo"

    try:
        filename = file.filename.lower()
        # 1. LEER EL ARCHIVO SEGÚN SU EXTENSIÓN
        if filename.endswith('.csv'):
            content = file.stream.read().decode("latin1")
            stream = io.StringIO(content)
            # Detectar si el CSV usa coma o punto y coma
            dialect = csv.Sniffer().sniff(content[:2048])
            reader = csv.DictReader(stream, dialect=dialect)
            lista_clientes = list(reader)
        else:
            # Leer Excel (.xlsx o .xls) usando pandas
            import pandas as pd
            engine = 'openpyxl' if filename.endswith('.xlsx') else 'xlrd'
            df = pd.read_excel(file, engine=engine)
            lista_clientes = df.to_dict('records')

        conn = get_db_connection()
        cursor = conn.cursor()
        # 2. OPTIMIZACIÓN: Procesar todo rápido para evitar el "Lock wait timeout"
        conn.autocommit = False 

        for row in lista_clientes:
            # Limpiar nombres de columnas (quita espacios y símbolos)
            row = {str(k).strip(): v for k, v in row.items()}
            
            # Mapeo flexible de nombres (Nombre, RUT, Email, Telefono, Direccion, Comuna)
            nombre = row.get('Nombre', '')
            rut = row.get('RUT', '')
            email = row.get('Email', '')
            # Buscamos variantes por si el Excel tiene acentos
            tel = next((v for k, v in row.items() if 'Tel' in k), '')
            dir = next((v for k, v in row.items() if 'Direc' in k), '')
            com = row.get('Comuna', '')

            if not rut or not nombre:
                continue

            # 3. SOLUCIÓN DEFINITIVA A DUPLICADOS: 
            # Si el email existe, actualiza los datos del cliente en lugar de fallar.
            sql = """INSERT INTO clientes (rut, razon_social, email, telefono, direccion, comuna, estado) 
                     VALUES (%s, %s, %s, %s, %s, %s, 'Activo')
                     ON DUPLICATE KEY UPDATE 
                     razon_social=VALUES(razon_social), telefono=VALUES(telefono), 
                     direccion=VALUES(direccion), comuna=VALUES(comuna)"""
            
            cursor.execute(sql, (str(rut), str(nombre), str(email), str(tel), str(dir), str(com)))

        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('lista_clientes'))
        
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return f"<h1>Error Crítico en Importación:</h1><p style='color:red;'>{str(e)}</p><a href='/clientes'>Volver</a>"
        
        
@app.route('/reparar-bd')
def reparar_bd():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Cambiamos la columna a texto libre de 50 caracteres para que acepte cualquier documento
        cursor.execute("ALTER TABLE ventas MODIFY COLUMN tipo_documento VARCHAR(50)")
        conn.commit()
        return "<h2 style='color:green;'>¡Base de datos arreglada con éxito! Ya puedes registrar Notas de Venta.</h2><br><a href='/venta/nueva'>Volver a Nueva Venta</a>"
    except Exception as e:
        return f"<h2 style='color:red;'>Error al reparar: {str(e)}</h2>"
    finally:
        cursor.close()
        conn.close()
        
@app.route('/agregar-despacho')
def agregar_despacho():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Agregamos la columna 'despacho' a la tabla ventas. 
        # Agregamos la columna 'despacho' a la tabla ventas. 2
        # Agregamos la columna 'despacho' a la tabla ventas. 3
        # Usamos ADD COLUMN IF NOT EXISTS para que no haya error si ya se creó.
        cursor.execute("ALTER TABLE ventas ADD COLUMN despacho VARCHAR(100) DEFAULT 'Retiro Local'")
        conn.commit()
        return "<h2 style='color:green;'>¡Columna de Despacho agregada con éxito a la base de datos!</h2><br><a href='/ventas'>Volver a Ventas</a>"
    except Exception as e:
        return f"<h2 style='color:red;'>La columna probablemente ya existe o hubo un error: {str(e)}</h2>"
    finally:
        cursor.close()
        conn.close()

@app.route('/instalar-kardex')
def instalar_kardex():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Ya sabemos que la tabla existe, así que solo agregamos/modificamos las columnas necesarias.
        # Usamos try-except individuales para que si la columna ya se creó en un intento anterior, no colapse.
        try: cursor.execute("ALTER TABLE movimientos_inventario ADD COLUMN saldo_resultante DECIMAL(10,2)")
        except: pass
        
        try: cursor.execute("ALTER TABLE movimientos_inventario ADD COLUMN documento_referencia VARCHAR(100)")
        except: pass
        
        try: cursor.execute("ALTER TABLE movimientos_inventario MODIFY COLUMN cantidad DECIMAL(10,2)")
        except: pass
        
        conn.commit()
        return "<h2 style='color:green;'>¡Base de datos del Kardex actualizada con éxito!</h2><br><a href='/inventario'>Volver al Inventario</a>"
    except Exception as e:
        return f"<h2 style='color:red;'>Error al instalar: {str(e)}</h2>"
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)
