import io
import json
import math
from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from django.views.decorators.csrf import csrf_exempt
from .models import SimulationResult
from .propagation_engine import PropagationEngine

def index(request):
    return render(request, 'simulator/index.html')

@csrf_exempt
def simulate_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            tx_lat = float(data['tx_lat'])
            tx_lng = float(data['tx_lng'])
            rx_lat = float(data['rx_lat'])
            rx_lng = float(data['rx_lng'])
            
            frequency_mhz = float(data['frequency_mhz'])
            tx_power_dbm = float(data['tx_power_dbm'])
            tx_gain_dbi = float(data['tx_gain_dbi'])
            rx_gain_dbi = float(data['rx_gain_dbi'])
            tx_cable_loss = float(data.get('tx_cable_loss', 0.0))
            rx_cable_loss = float(data.get('rx_cable_loss', 0.0))
            environment = data.get('environment', 'Rural')
            ant_height_tx = float(data.get('ant_height_tx', 15.0))
            ant_height_rx = float(data.get('ant_height_rx', 3.0))
            sf = int(data.get('sf', 7))
            bw_hz = int(data.get('bw_hz', 125000))
            
            # Run simulation
            results = PropagationEngine.simulate(
                tx_lat, tx_lng, rx_lat, rx_lng,
                frequency_mhz, tx_power_dbm, tx_gain_dbi, rx_gain_dbi,
                sf, bw_hz, tx_cable_loss, rx_cable_loss, environment,
                ant_height_tx, ant_height_rx
            )
            
            # Save to DB
            sim_record = SimulationResult.objects.create(
                user=request.user if request.user.is_authenticated else None,
                tx_lat=tx_lat, tx_lng=tx_lng, rx_lat=rx_lat, rx_lng=rx_lng,
                frequency_mhz=frequency_mhz, tx_power_dbm=tx_power_dbm,
                tx_gain_dbi=tx_gain_dbi, rx_gain_dbi=rx_gain_dbi,
                tx_cable_loss=tx_cable_loss, rx_cable_loss=rx_cable_loss,
                environment=environment,
                sf=sf, bw_hz=bw_hz,
                distance_km=results['distance_km'],
                fspl_db=results['fspl_db'],
                obstruction_loss_db=results['obstruction_loss_db'],
                fresnel_status=results['fresnel_status'],
                rx_power_dbm=results['rx_power_dbm'],
                link_ok=results['link_ok']
            )
            
            return JsonResponse({
                'status': 'success',
                'results': results,
                'id': sim_record.id
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

def history_api(request):
    if request.user.is_authenticated:
        history = SimulationResult.objects.filter(user=request.user).order_by('-created_at')[:10]
    else:
        history = SimulationResult.objects.filter(user__isnull=True).order_by('-created_at')[:10]
    
    data = []
    for item in history:
        data.append({
            'id': item.id,
            'frequency_mhz': item.frequency_mhz,
            'distance_km': round(item.distance_km, 2),
            'rx_power_dbm': round(item.rx_power_dbm, 2),
            'link_ok': item.link_ok,
            'created_at': item.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    return JsonResponse({'status': 'success', 'history': data})

def export_pdf(request, sim_id):
    try:
        sim = SimulationResult.objects.get(id=sim_id)
        if request.user.is_authenticated and sim.user and sim.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Not authorized'}, status=403)
            
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Draw Header
        p.setFillColorRGB(0.1, 0.25, 0.45) # Dark Blue
        p.rect(0, 10.2 * inch, 8.5 * inch, 0.8 * inch, fill=1, stroke=0)
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica-Bold", 18)
        p.drawString(0.8 * inch, 10.5 * inch, "INFORME TÉCNICO: SIMULACIÓN LORAWAN")
        
        # Info text
        p.setFillColorRGB(0.4, 0.4, 0.4)
        p.setFont("Helvetica", 10)
        p.drawString(0.8 * inch, 9.7 * inch, f"Fecha de Simulación: {sim.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if sim.user:
            p.drawString(4.5 * inch, 9.7 * inch, f"Usuario: {sim.user.username}")
            
        def draw_card(title, y_pos, height, data_dict):
            # Draw rounded rect background
            p.setFillColorRGB(0.96, 0.97, 0.98)
            p.setStrokeColorRGB(0.85, 0.85, 0.88)
            p.roundRect(0.8 * inch, y_pos, 6.9 * inch, height, 8, fill=1, stroke=1)
            
            # Title bar
            p.setFillColorRGB(0.2, 0.4, 0.6) # Slate blue
            p.roundRect(0.8 * inch, y_pos + height - 0.3*inch, 6.9 * inch, 0.3*inch, 8, fill=1, stroke=0)
            # Fill the bottom corners to make it flat at bottom (join with body)
            p.rect(0.8 * inch, y_pos + height - 0.3*inch, 6.9 * inch, 0.15*inch, fill=1, stroke=0)
            
            p.setFillColorRGB(1, 1, 1)
            p.setFont("Helvetica-Bold", 11)
            p.drawString(1.0 * inch, y_pos + height - 0.22*inch, title)
            
            # Data rendering
            current_y = y_pos + height - 0.55 * inch
            col1_x = 1.0 * inch
            col2_x = 4.4 * inch
            is_col1 = True
            
            for key, val in data_dict.items():
                x = col1_x if is_col1 else col2_x
                p.setFillColorRGB(0.3, 0.3, 0.3)
                p.setFont("Helvetica-Bold", 10)
                p.drawString(x, current_y, f"{key}:")
                
                p.setFillColorRGB(0.1, 0.1, 0.1)
                p.setFont("Helvetica", 10)
                p.drawString(x + 1.6*inch, current_y, str(val))
                
                if not is_col1:
                    current_y -= 0.28 * inch
                is_col1 = not is_col1

        # Card 1: Coordenadas
        draw_card("Coordenadas y Ubicación", 8.0 * inch, 1.3 * inch, {
            "Transmisor (TX)": f"{sim.tx_lat:.5f}, {sim.tx_lng:.5f}",
            "Receptor (RX)": f"{sim.rx_lat:.5f}, {sim.rx_lng:.5f}",
            "Distancia Total": f"{sim.distance_km:.2f} km",
            "Tipo de Entorno": sim.environment
        })
        
        # Card 2: Parametros Tecnicos
        draw_card("Parámetros Técnicos del Radio", 6.0 * inch, 1.7 * inch, {
            "Frecuencia (MHz)": f"{sim.frequency_mhz} MHz",
            "Spreading Factor": sim.sf,
            "Bandwidth (BW)": f"{sim.bw_hz / 1000} kHz",
            "Potencia Emisión": f"{sim.tx_power_dbm} dBm",
            "Ganancia Ant. TX": f"{sim.tx_gain_dbi} dBi",
            "Ganancia Ant. RX": f"{sim.rx_gain_dbi} dBi",
            "Pérdida Cable TX": f"{sim.tx_cable_loss} dB",
            "Pérdida Cable RX": f"{sim.rx_cable_loss} dB"
        })
        
        # Loss calculations
        extra_env_losses = {'Rural': 15.0, 'Suburbano': 20.0, 'Bosque': 25.0, 'Urbano': 35.0}
        env_loss_val = extra_env_losses.get(sim.environment, 15.0)
        total_loss = sim.tx_cable_loss + sim.rx_cable_loss + sim.obstruction_loss_db + env_loss_val
        
        # Card 3: Resultados
        draw_card("Resultados de Propagación Estimada", 4.0 * inch, 1.7 * inch, {
            "Pérdida FSPL": f"{sim.fspl_db:.2f} dB",
            "Pérdida Entorno": f"{env_loss_val:.2f} dB",
            "Atenuación Obstác.": f"{sim.obstruction_loss_db:.2f} dB",
            "Atenuación Extra Tot.": f"{total_loss:.2f} dB",
            "Zona de Fresnel": sim.fresnel_status,
            "": "",
            "Potencia Recibida": f"{sim.rx_power_dbm:.2f} dBm"
        })
        
        # Status Badge
        if sim.link_ok:
            p.setFillColorRGB(0.9, 1.0, 0.9)
            p.setStrokeColorRGB(0.2, 0.7, 0.2)
            p.roundRect(0.8 * inch, 2.7 * inch, 6.9 * inch, 0.8 * inch, 8, fill=1, stroke=1)
            p.setFillColorRGB(0.1, 0.5, 0.1)
            p.setFont("Helvetica-Bold", 16)
            p.drawCentredString(4.25 * inch, 3.05 * inch, "ESTADO DEL ENLACE: VIABLE (OK)")
        else:
            p.setFillColorRGB(1.0, 0.9, 0.9)
            p.setStrokeColorRGB(0.8, 0.2, 0.2)
            p.roundRect(0.8 * inch, 2.7 * inch, 6.9 * inch, 0.8 * inch, 8, fill=1, stroke=1)
            p.setFillColorRGB(0.7, 0.1, 0.1)
            p.setFont("Helvetica-Bold", 16)
            p.drawCentredString(4.25 * inch, 3.05 * inch, "ESTADO DEL ENLACE: SIN COBERTURA (FALLO)")
        
        p.setFillColorRGB(0.4, 0.4, 0.4)
        p.setFont("Helvetica", 9)

        
        # ── PAGINA 2: Perfil de Elevacion LOS ───────────────────────────────
        p.showPage()
        
        # Draw Header Page 2
        p.setFillColorRGB(0.1, 0.25, 0.45)
        p.rect(0, 10.2 * inch, 8.5 * inch, 0.8 * inch, fill=1, stroke=0)
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica-Bold", 18)
        p.drawString(0.8 * inch, 10.5 * inch, "ANÁLISIS TOPOGRÁFICO DE LÍNEA DE VISTA (LOS)")
        
        p.setFillColorRGB(0.3, 0.3, 0.3)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(1 * inch, 9.6 * inch, "Perfil de Elevación del Terreno")
        
        p.setFont("Helvetica", 9)
        p.setFillColorRGB(0.5, 0.5, 0.5)
        p.drawString(1 * inch, 9.4 * inch,
            "Reconstrucción topográfica a lo largo de la trayectoria de la señal con Zona de Fresnel modelada.")
        p.setFillColorRGB(0, 0, 0)
        
        # Re-calcular perfil para la segunda pagina
        try:
            elev_profile, _obs, _fst = PropagationEngine.get_elevation_profile(
                sim.tx_lat, sim.tx_lng, sim.rx_lat, sim.rx_lng,
                sim.frequency_mhz, sim.distance_km, num_points=100
            )
        except Exception:
            elev_profile = []
        
        if elev_profile:
            # --- Mini grafico de barras ASCII en el PDF ---
            chart_x = 1 * inch
            chart_y_bottom = 5.5 * inch
            chart_width = 6.5 * inch
            chart_height = 4.0 * inch
            
            elevs = [pt["elevation"] for pt in elev_profile]
            los_pts = [pt["los_elevation"] for pt in elev_profile]
            f_rad = [pt["fresnel_radius"] for pt in elev_profile]
            
            n = len(elev_profile)
            f_upper = [los_pts[i] + f_rad[i] for i in range(n)]
            f_lower = [los_pts[i] - f_rad[i] for i in range(n)]
            dists = [pt["distance"] for pt in elev_profile]
            
            min_e = min(min(elevs), min(f_lower)) - 10
            max_e = max(max(elevs), max(f_upper)) + 30
            range_e = max_e - min_e if (max_e - min_e) > 0 else 1
            
            def to_px_y(val):
                return chart_y_bottom + ((val - min_e) / range_e) * chart_height
            
            def to_px_x(i):
                return chart_x + (i / (n - 1)) * chart_width if n > 1 else chart_x
            
            # Fondo del grafico
            p.setFillColorRGB(0.98, 0.98, 0.98)
            p.rect(chart_x, chart_y_bottom, chart_width, chart_height, fill=1, stroke=0)
            
            # Gridlines (X and Y)
            p.setStrokeColorRGB(0.85, 0.85, 0.85)
            p.setLineWidth(0.5)
            p.setDash([2, 2])
            
            # Y Gridlines
            for tick_val in [min_e, min_e + range_e * 0.25, min_e + range_e * 0.5, min_e + range_e * 0.75, max_e]:
                tick_y = to_px_y(tick_val)
                p.line(chart_x, tick_y, chart_x + chart_width, tick_y)
                
            # X Gridlines
            for i in [0, n // 4, n // 2, 3 * n // 4, n - 1]:
                tick_x = to_px_x(i)
                p.line(tick_x, chart_y_bottom, tick_x, chart_y_bottom + chart_height)
            p.setDash([])
            
            # Zona Fresnel 100% (elipse completa con transparencia)
            if "Severo" in sim.fresnel_status:
                p.setFillColor(colors.Color(0.8, 0.2, 0.2, alpha=0.3))  # Rojo claro (Obstruido)
                fresnel_stroke = (0.8, 0.2, 0.2)
            elif "Parcial" in sim.fresnel_status or "Leve" in sim.fresnel_status:
                p.setFillColor(colors.Color(0.8, 0.8, 0.1, alpha=0.3)) # Amarillo claro (Parcial)
                fresnel_stroke = (0.8, 0.6, 0.0)
            else:
                p.setFillColor(colors.Color(0.2, 0.7, 0.2, alpha=0.25)) # Verde claro (Despejado)
                fresnel_stroke = (0.2, 0.7, 0.2)
                
            fresnel_path = p.beginPath()
            fresnel_path.moveTo(to_px_x(0), to_px_y(f_upper[0]))
            for i in range(n):
                fresnel_path.lineTo(to_px_x(i), to_px_y(f_upper[i]))
            for i in range(n - 1, -1, -1):
                fresnel_path.lineTo(to_px_x(i), to_px_y(f_lower[i]))
            fresnel_path.close()
            p.drawPath(fresnel_path, fill=1, stroke=0)
            
            # Relleno de terreno (area entre base y elevacion, tapa parte inferior de Fresnel)
            p.setFillColorRGB(0.55, 0.37, 0.18)
            terrain_path = p.beginPath()
            terrain_path.moveTo(to_px_x(0), chart_y_bottom)
            for i, pt in enumerate(elev_profile):
                terrain_path.lineTo(to_px_x(i), to_px_y(pt["elevation"]))
            terrain_path.lineTo(to_px_x(n - 1), chart_y_bottom)
            terrain_path.close()
            p.drawPath(terrain_path, fill=1, stroke=0)
            
            # Borde del terreno para que resalte
            p.setStrokeColorRGB(0.4, 0.25, 0.1)
            p.setLineWidth(1.0)
            p.setDash([])
            for i in range(n - 1):
                p.line(to_px_x(i), to_px_y(elevs[i]), to_px_x(i + 1), to_px_y(elevs[i + 1]))

            # Linea LOS (verde o roja dependiendo de link_ok)
            if sim.link_ok:
                p.setStrokeColorRGB(0.1, 0.7, 0.1)
            else:
                p.setStrokeColorRGB(0.8, 0.1, 0.1)
            p.setLineWidth(1.5)
            p.setDash([5, 4])
            for i in range(n - 1):
                p.line(to_px_x(i), to_px_y(los_pts[i]), to_px_x(i + 1), to_px_y(los_pts[i + 1]))
            
            # Lineas de bordes de Fresnel (punteadas)
            p.setStrokeColorRGB(*fresnel_stroke)
            p.setLineWidth(0.8)
            p.setDash([2, 2])
            for i in range(n - 1):
                # Superior
                p.line(to_px_x(i), to_px_y(f_upper[i]), to_px_x(i + 1), to_px_y(f_upper[i + 1]))
                # Inferior
                p.line(to_px_x(i), to_px_y(f_lower[i]), to_px_x(i + 1), to_px_y(f_lower[i + 1]))
            
            # Borde del grafico
            p.setStrokeColorRGB(0.4, 0.4, 0.4)
            p.setLineWidth(0.5)
            p.setDash([])
            p.rect(chart_x, chart_y_bottom, chart_width, chart_height, fill=0, stroke=1)
            
            # Eje Y: etiquetas de elevacion
            p.setFont("Helvetica", 7)
            p.setFillColorRGB(0, 0, 0)
            for tick_val in [min_e, min_e + range_e * 0.25, min_e + range_e * 0.5, min_e + range_e * 0.75, max_e]:
                tick_y = to_px_y(tick_val)
                p.drawString(chart_x - 0.5 * inch, tick_y - 3, f"{tick_val:.0f}m")
            
            # Eje X: etiquetas de distancia
            for i in [0, n // 4, n // 2, 3 * n // 4, n - 1]:
                tick_x = to_px_x(i)
                p.setFillColorRGB(0, 0, 0)
                p.drawString(tick_x - 10, chart_y_bottom - 12, f"{dists[i]:.1f}km")
            
            # Leyenda
            p.setFont("Helvetica", 8)
            p.setFillColorRGB(0.55, 0.37, 0.18)
            p.drawString(chart_x, chart_y_bottom - 25, "■ Terreno")
            p.setFillColorRGB(0.1, 0.7, 0.1) if sim.link_ok else p.setFillColorRGB(0.8, 0.1, 0.1)
            p.drawString(chart_x + 1.2 * inch, chart_y_bottom - 25, "--- LOS (Linea de Vista)")
            p.setFillColorRGB(*fresnel_stroke)
            p.drawString(chart_x + 3.2 * inch, chart_y_bottom - 25, "··· Zona de Fresnel 100%")
            
            # --- Tabla de datos topograficos ---
            p.setFont("Helvetica-Bold", 12)
            p.setFillColorRGB(0, 0, 0)
            table_y = chart_y_bottom - 0.7 * inch
            p.drawString(1 * inch, table_y, "Tabla de Datos Topográficos (Muestra Representativa)")
            
            table_y -= 0.3 * inch
            headers = ["Distancia (km)", "Elev. Terreno", "Línea de Vista", "Radio Fresnel", "Estado Local"]
            col_centers = [1.6*inch, 2.9*inch, 4.25*inch, 5.6*inch, 6.9*inch]
            
            # Header Row
            p.setFillColorRGB(0.1, 0.25, 0.45) # Dark Blue
            p.roundRect(0.95*inch, table_y - 4, 6.6*inch, 18, 4, fill=1, stroke=0)
            p.setFillColorRGB(1, 1, 1)
            p.setFont("Helvetica-Bold", 10)
            for hi, hdr in enumerate(headers):
                p.drawCentredString(col_centers[hi], table_y + 2, hdr)
            
            # Vertical lines array for separators
            sep_xs = [2.25*inch, 3.55*inch, 4.95*inch, 6.25*inch]
            
            table_y -= 0.18 * inch
            p.setFont("Helvetica", 8)
            
            step = max(1, len(elev_profile) // 15)
            table_profile = elev_profile[::step][:15]
            
            for idx, pt in enumerate(table_profile):
                terrain_e = pt["elevation"]
                los_e = pt["los_elevation"]
                fr = pt["fresnel_radius"]
                f60_e = pt["fresnel_60_elevation"]
                
                # Estado de este punto
                if terrain_e > los_e:
                    estado = "BLOQUEADO"
                    col_status = (0.8, 0.1, 0.1)
                elif terrain_e > f60_e:
                    estado = "OBSTR. 60%"
                    col_status = (0.8, 0.5, 0.0)
                elif terrain_e > (los_e - fr):
                    estado = "OBSTR. LEVE"
                    col_status = (0.7, 0.7, 0.0)
                else:
                    estado = "DESPEJADO"
                    col_status = (0.1, 0.6, 0.1)
                
                # Fila alternada
                if idx % 2 == 0:
                    p.setFillColorRGB(0.94, 0.94, 0.94) # Light pure gray
                else:
                    p.setFillColorRGB(1, 1, 1)
                p.setStrokeColorRGB(0.85, 0.85, 0.85)
                p.setLineWidth(0.5)
                p.rect(0.95*inch, table_y - 3, 6.6*inch, 14, fill=1, stroke=0)
                
                # Draw vertical separators
                for sx in sep_xs:
                    p.line(sx, table_y - 3, sx, table_y + 11)
                
                # Data Text
                p.setFillColorRGB(0, 0, 0)
                p.setFont("Helvetica", 9)
                p.drawCentredString(col_centers[0], table_y + 1, f"{pt['distance']:.2f}")
                p.drawCentredString(col_centers[1], table_y + 1, f"{terrain_e:.1f} m")
                p.drawCentredString(col_centers[2], table_y + 1, f"{los_e:.1f} m")
                p.drawCentredString(col_centers[3], table_y + 1, f"{fr:.1f} m")
                
                # Estado con color
                p.setFillColorRGB(*col_status)
                p.setFont("Helvetica-Bold", 8)
                p.drawCentredString(col_centers[4], table_y + 1, estado)
                p.setFont("Helvetica", 8)
                
                table_y -= 0.18 * inch
                if table_y < 0.5 * inch:
                    break  # Evitar salirse de pagina
        else:
            p.setFont("Helvetica", 11)
            p.setFillColorRGB(0.5, 0.5, 0.5)
            p.drawString(1 * inch, 5 * inch, "No se pudo obtener el perfil de elevacion en este momento.")
            p.drawString(1 * inch, 4.75 * inch, "(Verifique la conexion a Internet o intente de nuevo.)")
            p.setFillColorRGB(0, 0, 0)
        
        p.setFont("Helvetica", 8)
        p.setFillColorRGB(0.5, 0.5, 0.5)
        p.drawString(1 * inch, 0.5 * inch, ".")
        p.setFillColorRGB(0, 0, 0)
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename=f"informe_lora_{sim.id}.pdf")
        
    except SimulationResult.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Simulacion no encontrada'}, status=404)
