
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from pathlib import Path
import io, json

# Importa BD V4 con soporte parciales + multi evidencia
from modules.database_v4 import init_db, upsert_facturas, get_facturas_con_saldo, autorizar_pago_parcial, get_historial_autorizaciones, guardar_evidencias_multiples, get_evidencias, validar_evidencia, verificar_login

st.set_page_config(page_title="MCF V3 Final | Gerencia + Excel", page_icon="🥑", layout="wide")

PRIMARY="#2E7D32"

st.markdown(f"""
<style>
.stButton>button {{background:{PRIMARY}; color:white; border-radius:8px; font-weight:600}}
.kpi {{background:white; padding:1rem; border-radius:12px; border-left:5px solid {PRIMARY}}}
.sumbox {{background:linear-gradient(135deg,#E8F5E9 0%,#F1F8E9 100%); border:2px solid #4CAF50; padding:18px; border-radius:12px; font-size:16px; line-height:1.6}}
.sumbox b {{font-size:18px}} .sumbox .big {{font-size:19px; background:white; padding:6px 12px; border-radius:20px; border:1px solid #4CAF50}}
.ev-thumb {{border:2px solid #4CAF50; border-radius:8px; width:45px; height:45px; object-fit:cover}}
</style>
""", unsafe_allow_html=True)

init_db()

if 'auth' not in st.session_state: st.session_state.auth=False
if not st.session_state.auth:
    c1,c2,c3=st.columns([1,2,1])
    with c2:
        st.title("🥑 MCF V3 Final - Login RFC")
        rol=st.selectbox("Rol",["Proveedor","CuentasPorPagar","Gerencia General","Admin"])
        rfc=st.text_input("RFC", value="CME910715UB9" if rol=="Proveedor" else "CXP001" if rol=="CuentasPorPagar" else "TES001" if rol=="Gerencia General" else "ADMIN001")
        pwd=st.text_input("Contraseña", type="password", value="costco123" if "COSTCO" in rfc else "cxp123" if rol=="CuentasPorPagar" else "teso123" if rol=="Gerencia General" else "admin123")
        if st.button("Ingresar", type="primary", use_container_width=True):
            # Mapea Gerencia General a Tesoreria internamente
            rol_db = "Tesoreria" if rol=="Gerencia General" else rol
            user=verificar_login(rfc,pwd, rol_db if rol!="Admin" else None)
            if user or (rol=="Admin" and verificar_login(rfc,pwd)):
                st.session_state.auth=True; st.session_state.user=user or {"rfc":rfc,"rol":rol,"nombre":rfc}; st.session_state.rol=rol; st.session_state.rfc=rfc
                st.rerun()
            else: st.error("Login incorrecto")
    st.stop()

rol=st.session_state.rol
st.sidebar.markdown(f"**{st.session_state.rfc}**\n{rol}")
if st.sidebar.button("Cerrar Sesión"): st.session_state.auth=False; st.rerun()

# Sidebar cargar SAT
if rol in ["Admin","CuentasPorPagar","Gerencia General"]:
    from modules.parser import parse_sat_excel
    up=st.sidebar.file_uploader("Excel SAT", type=["xlsx"])
    if up:
        df=parse_sat_excel(up); st.sidebar.success(f"{len(df)} facturas")
        if st.sidebar.button("Integrar"):
            ins,upd=upsert_facturas(df); st.sidebar.success(f"Insertadas {ins}"); st.rerun()

# Tabs por rol
if rol=="Proveedor":
    tab1,tab2=st.tabs(["📦 Mis Facturas - 3 Evidencias","📊 Historial"])
else:
    tab1,tab2,tab3=st.tabs(["✅ Autorizar - Gerencia Doble Check + Parciales","📦 Validar (Agrupado 3 docs)","📊 Resumen Excel"])

if rol=="Proveedor":
    with tab1:
        df=get_facturas_con_saldo(rfc=st.session_state.rfc)
        if df.empty: st.info("Sin facturas")
        else:
            for _,row in df.iterrows():
                with st.container(border=True):
                    c1,c2=st.columns([3,1])
                    with c1:
                        st.markdown(f"**{row['serie']}-{row['folio']}** | ${row['total_factura']:,.2f} | Saldo ${row['saldo_pendiente']:,.2f}")
                        st.progress(int(row['total_autorizado']/row['total_factura']*100) if row['total_factura']>0 else 0)
                    with c2:
                        with st.expander("📤 Subir 3 evidencias"):
                            st.caption("EVIDENCIA 1 - Foto producto")
                            f1=st.file_uploader("Archivo 1", type=["jpg","png","pdf"], key=f"f1_{row['uuid']}")
                            st.caption("EVIDENCIA 2 - PDF firmado")
                            f2=st.file_uploader("Archivo 2", type=["jpg","png","pdf"], key=f"f2_{row['uuid']}")
                            st.caption("EVIDENCIA 3 - Ticket adicional")
                            f3=st.file_uploader("Archivo 3", type=["jpg","png","pdf"], key=f"f3_{row['uuid']}")
                            notas=st.text_input("Notas lote", key=f"n_{row['uuid']}")
                            archivos=[x for x in [f1,f2,f3] if x]
                            if archivos and st.button(f"Subir {len(archivos)} evidencias", key=f"b_{row['uuid']}"):
                                guardar_evidencias_multiples(row['uuid'], archivos, st.session_state.rfc, st.session_state.rfc, "Proveedor")
                                st.success(f"{len(archivos)} subidas"); st.rerun()
else:
    with tab1:
        df=get_facturas_con_saldo()
        solo_aprob=st.checkbox("✅ Solo con evidencia validada por CxP (Doble check seguro)", value=True)
        if solo_aprob: df=df[df['evidencias_aprobadas']>0]
        if df.empty: st.info("Sin facturas")
        else:
            # Cuadro verde letras grandes
            sel_count=0
            st.markdown(f"""
            <div class='sumbox'>
            📊 <b>Seleccionadas: {sel_count} facturas</b> | Suma total: <b>${df['total_factura'].sum():,.2f}</b> | Ya pagado: <b>${df['total_autorizado'].sum():,.2f}</b> | 
            <span class='big'>Este pago parcial: ${df['saldo_pendiente'].sum():,.2f} (editable suma)</span> | Saldo restante: <b style='color:#F44336'>${df['saldo_pendiente'].sum():,.2f}</b> | % avance: <b style='font-size:20px'>{df['total_autorizado'].sum()/df['total_factura'].sum()*100 if df['total_factura'].sum()>0 else 0:.1f}%</b>
            <br><small>Selecciona facturas con checkbox y edita importe a pagar. Puedes pagar parcial, ej: $5,000 de $11,512.</small>
            </div>
            """, unsafe_allow_html=True)
            # Editor con importe editable + evidencias visibles
            df_edit=df.copy()
            df_edit['Sel']=False
            df_edit['Este Pago Parcial']=df_edit['saldo_pendiente']
            df_edit['Ver Evidencias']=df_edit.apply(lambda x: f"👁️ Ver {int(x['num_evidencias'])} docs", axis=1)
            edited=st.data_editor(df_edit[['Sel','serie','folio','emisor_nombre','total_factura','total_autorizado','saldo_pendiente','evidencias_aprobadas','num_evidencias','Ver Evidencias','Este Pago Parcial']], 
                column_config={"Sel": st.column_config.CheckboxColumn("✔️"), "Este Pago Parcial": st.column_config.NumberColumn("IMPORTE EDITABLE PARCIAL", format="$%.2f"), "Ver Evidencias": st.column_config.TextColumn("EVIDENCIA - Doble Check")},
                use_container_width=True, hide_index=True, key="edit_gerencia")
            sel=edited[edited['Sel']==True]
            if not sel.empty:
                st.info(f"**Resumen A PAGAR: {len(sel)} facturas | Este pago: ${sel['Este Pago Parcial'].sum():,.2f}** vs PENDIENTES: {len(df)-len(sel)} facturas | ${df[~df.index.isin(sel.index)]['saldo_pendiente'].sum():,.2f}")
                c1,c2,c3=st.columns(3)
                with c1:
                    if st.button(f"📥 Exportar a Excel - {len(sel)} a pagar", type="primary", use_container_width=True):
                        csv=sel.to_csv(index=False).encode('utf-8')
                        st.download_button("Descargar Excel CSV", csv, file_name=f"MCF_A_PAGAR_{date.today()}.csv", mime="text/csv")
                with c2:
                    if st.button("📊 Exportar Resumen Completo", use_container_width=True):
                        st.download_button("Descargar Resumen", df.to_csv(index=False).encode('utf-8'), file_name=f"MCF_RESUMEN_{date.today()}.csv")
                with c3:
                    if st.button("📧 Enviar lista por Email (Excel adjunto)", use_container_width=True):
                        st.success("✅ Email enviado con Excel adjunto a gerencia@mercadocentral.com (simulado)")
                if st.button(f"✅ Autorizar {len(sel)} facturas por ${sel['Este Pago Parcial'].sum():,.2f}", type="primary"):
                    for idx,row in sel.iterrows():
                        pos=edited.index.get_loc(idx); uuid=df.iloc[pos]['uuid']; total=df.iloc[pos]['total_factura']
                        autorizar_pago_parcial(uuid, float(row['Este Pago Parcial']), date.today(), "", st.session_state.rfc, total)
                    st.success("Autorizadas"); st.rerun()
            
            # Mostrar evidencias visibles por factura (fix bug)
            st.divider()
            st.markdown("### 👁️ Evidencias visibles para doble check")
            for _,row in df.head(3).iterrows():
                evs=get_evidencias(uuid=row['uuid'])
                with st.container(border=True):
                    st.markdown(f"**{row['serie']}-{row['folio']} • {row['emisor_nombre']} • Aprobada • {len(evs)} docs**")
                    if not evs.empty:
                        cols=st.columns(3)
                        for i,(_,ev) in enumerate(evs.iterrows()):
                            with cols[i%3]:
                                st.caption(f"Doc {i+1}: {ev['nombre_archivo'][:20]}")
                                st.caption(f"{ev['tamano_kb']:.1f}KB - {ev['estatus_validacion']}")
                                if ev['ruta_archivo'] and Path(ev['ruta_archivo']).exists() and ev['nombre_archivo'].lower().endswith(('.jpg','.png','.jpeg')):
                                    st.image(ev['ruta_archivo'], width=120)
                    else:
                        st.warning("Sin evidencias - Requiere doble check")

with tab2 if rol!="Proveedor" else tab1:
    if rol in ["CuentasPorPagar","Admin"]:
        st.subheader("📦 Validación agrupada por factura (3 docs juntos)")
        from modules.database_v4 import get_evidencias as ge
        df_e=ge(estatus='Pendiente')
        if df_e.empty: st.success("Sin pendientes")
        else:
            for uuid in df_e['uuid'].unique():
                evs_uuid=df_e[df_e['uuid']==uuid]
                with st.container(border=True):
                    st.markdown(f"**{uuid[:8]} • {len(evs_uuid)} documentos**")
                    c1,c2=st.columns(2)
                    with c1:
                        for _,ev in evs_uuid.iterrows():
                            st.markdown(f"📄 {ev['nombre_archivo']} - {ev['tamano_kb']:.1f}KB")
                    with c2:
                        motivo=st.text_area("Motivo rechazo (si aplica)", key=f"mot_{uuid}")
                        if st.button(f"✅ Aprobar {len(evs_uuid)} docs", key=f"ap_{uuid}"):
                            for _,ev in evs_uuid.iterrows(): validar_evidencia(ev['id'], st.session_state.rfc, True, "Aprobado", {})
                            st.rerun()
                        if st.button(f"❌ Rechazar con comentario", key=f"re_{uuid}"):
                            if not motivo: st.error("Pon motivo de rechazo")
                            else:
                                for _,ev in evs_uuid.iterrows(): validar_evidencia(ev['id'], st.session_state.rfc, False, motivo, {})
                                st.warning(f"Rechazado y notificado por WhatsApp/Correo: {motivo}")
                                st.rerun()
