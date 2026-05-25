import math
import requests
from geopy.distance import geodesic

class PropagationEngine:
    @staticmethod
    def calculate_distance(tx_coords, rx_coords):
        """Calculates distance in km between two coords (lat, lon)."""
        return geodesic(tx_coords, rx_coords).kilometers

    @staticmethod
    def calculate_lora_sensitivity(sf, bw_hz):
        """
        Sensibilidad (dBm) = -174 + 10 * log10(BW_Hz) + NF + SNR
        Asumiendo NF = 6 dB
        """
        snr_table = {
            7: -7.5,
            8: -10.0,
            9: -12.5,
            10: -15.0,
            11: -17.5,
            12: -20.0
        }
        snr = snr_table.get(int(sf), -20.0)
        nf = 6.0
        return -174 + 10 * math.log10(bw_hz) + nf + snr

    @staticmethod
    def calculate_fspl(frequency_mhz, distance_km):
        """
        Free Space Path Loss formula
        L = 32.44 + 20*log10(f_MHz) + 20*log10(d_km)
        """
        if distance_km <= 0:
            return 0 # Prevent log(0) error if points are exactly the same
        return 32.44 + 20 * math.log10(frequency_mhz) + 20 * math.log10(distance_km)

    @staticmethod
    def calculate_received_power(tx_power_dbm, tx_gain_dbi, rx_gain_dbi, fspl_db, tx_cable_loss=0, rx_cable_loss=0, obstruction_loss=0):
        """
        Prx = Ptx + Gtx + Grx - FSPL - Cables - Obstruction
        """
        return tx_power_dbm + tx_gain_dbi + rx_gain_dbi - fspl_db - tx_cable_loss - rx_cable_loss - obstruction_loss

    @staticmethod
    def evaluate_link(rx_power_dbm, sensitivity_dbm):
        """
        Returns True if Prx >= Sensitivity, otherwise False
        """
        return rx_power_dbm >= sensitivity_dbm

    @staticmethod
    def calculate_max_range(frequency_mhz, tx_power_dbm, tx_gain_dbi, rx_gain_dbi, sensitivity_dbm, extra_loss=0):
        margin = tx_power_dbm + tx_gain_dbi + rx_gain_dbi - sensitivity_dbm - 32.44 - 20 * math.log10(frequency_mhz) - extra_loss
        return 10 ** (margin / 20.0)

    @classmethod
    def simulate(cls, tx_lat, tx_lng, rx_lat, rx_lng, frequency_mhz, tx_power_dbm, tx_gain_dbi, rx_gain_dbi,
                 sf, bw_hz, tx_cable_loss, rx_cable_loss, environment='Rural',
                 ant_height_tx=15.0, ant_height_rx=3.0):
        distance_km = cls.calculate_distance((tx_lat, tx_lng), (rx_lat, rx_lng))
        fspl_db = cls.calculate_fspl(frequency_mhz, distance_km)
        
        # Pérdida extra por entorno empírico (Okumura-Hata simplificado)
        env_losses = {
            'Rural':     15.0,
            'Suburbano': 20.0,
            'Bosque':    25.0,
            'Urbano':    35.0
        }
        env_loss = env_losses.get(environment, 15.0)
        
        # Obtener Perfil de Elevación con altura de antena real
        elevation_profile, obstruction_loss, fresnel_status = cls.get_elevation_profile(
            tx_lat, tx_lng, rx_lat, rx_lng, frequency_mhz, distance_km,
            tx_ant_height=ant_height_tx, rx_ant_height=ant_height_rx
        )
        
        total_extra_loss = obstruction_loss + env_loss
        
        rx_power_dbm = cls.calculate_received_power(tx_power_dbm, tx_gain_dbi, rx_gain_dbi, fspl_db, tx_cable_loss, rx_cable_loss, total_extra_loss)
        
        sensitivity_dbm = cls.calculate_lora_sensitivity(sf, bw_hz)
        link_ok = cls.evaluate_link(rx_power_dbm, sensitivity_dbm)
        
        # Max range also needs to account for cable loss and environment loss
        fixed_losses = tx_cable_loss + rx_cable_loss + env_loss
        max_range_km = cls.calculate_max_range(frequency_mhz, tx_power_dbm, tx_gain_dbi, rx_gain_dbi, sensitivity_dbm, fixed_losses)
        
        return {
            "distance_km":       distance_km,
            "fspl_db":           fspl_db,
            "rx_power_dbm":      rx_power_dbm,
            "sensitivity_dbm":   sensitivity_dbm,
            "link_ok":           link_ok,
            "max_range_km":      max_range_km,
            "elevation_profile": elevation_profile,
            "obstruction_loss_db": obstruction_loss,
            "fresnel_status":    fresnel_status,
            "environment":       environment,
            "env_loss_db":       env_loss
        }

    @staticmethod
    def get_elevation_profile(tx_lat, tx_lng, rx_lat, rx_lng, frequency_mhz, total_distance_km,
                              num_points=100, tx_ant_height=15.0, rx_ant_height=15.0):
        """
        Genera el perfil de elevacion REAL entre TX y RX con analisis de Fresnel.
        - Muestrea 100 puntos de alta resolucion.
        - Utiliza Open-Meteo con fallback a Open-Elevation.
        """
        # --- Generar puntos intermedios ---
        points = []
        for i in range(num_points):
            fraction = i / (num_points - 1)
            lat = tx_lat + (rx_lat - tx_lat) * fraction
            lng = tx_lng + (rx_lng - tx_lng) * fraction
            points.append((lat, lng))

        elevations = None

        # Intento 1: Open-Meteo
        try:
            lats_str = ",".join([str(p[0]) for p in points])
            lngs_str = ",".join([str(p[1]) for p in points])
            url = f"https://api.open-meteo.com/v1/elevation?latitude={lats_str}&longitude={lngs_str}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                elevs = data.get('elevation', [])
                if len(elevs) == num_points:
                    elevations = elevs
        except Exception:
            pass

        # Intento 2: Open-Elevation (Fallback)
        if not elevations:
            try:
                payload = {"locations": [{"latitude": p[0], "longitude": p[1]} for p in points]}
                resp = requests.post("https://api.open-elevation.com/api/v1/lookup", json=payload, timeout=8)
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    if len(results) == num_points:
                        elevations = [float(r["elevation"]) for r in results]
            except Exception:
                pass

        # Si todo falla, asumimos terreno plano a nivel del mar
        if not elevations:
            elevations = [0] * num_points

        f_ghz = frequency_mhz / 1000.0

        # --- Altura absoluta de antenas TX/RX ---
        h_tx = elevations[0] + tx_ant_height
        h_rx = elevations[-1] + rx_ant_height

        # --- Contar puntos bloqueados (solo interiores) ---
        los_blocked    = 0   # cruza la linea de vista directa
        fresnel_blocked = 0  # invade la zona de Fresnel 60%
        interior_pts   = num_points - 2  # excluir extremos (d1=0 y d2=0)

        profile = []
        for i in range(num_points):
            d1 = geodesic((tx_lat, tx_lng), points[i]).kilometers
            d2 = max(total_distance_km - d1, 0.0)

            # Interpolacion lineal de la LOS en este punto
            t = i / (num_points - 1) if num_points > 1 else 0
            los_elev = h_tx + (h_rx - h_tx) * t

            # Radio de la 1ra Zona de Fresnel (metros)
            if d1 > 1e-6 and d2 > 1e-6 and f_ghz > 0 and total_distance_km > 0:
                fresnel_radius = 17.32 * math.sqrt((d1 * d2) / (f_ghz * total_distance_km))
            else:
                fresnel_radius = 0.0

            # Limite del 60% de Fresnel bajo la LOS
            fresnel_60_elev = los_elev - (0.6 * fresnel_radius)
            fresnel_60_elev_upper = los_elev + (0.6 * fresnel_radius)

            terrain_elev = elevations[i]

            # Analizar SOLO puntos interiores
            if 0 < i < num_points - 1 and interior_pts > 0:
                if terrain_elev >= los_elev:
                    los_blocked += 1
                elif terrain_elev >= fresnel_60_elev:
                    fresnel_blocked += 1

            profile.append({
                "distance":             round(d1, 4),
                "elevation":            terrain_elev,
                "los_elevation":        round(los_elev, 2),
                "fresnel_radius":       round(fresnel_radius, 2),
                "fresnel_60_elevation": round(fresnel_60_elev, 2),
                "fresnel_60_elevation_upper": round(fresnel_60_elev_upper, 2)
            })

        # --- Calcular porcentajes de bloqueo ---
        if interior_pts <= 0:
            interior_pts = 1
        pct_los     = los_blocked    / interior_pts
        pct_fresnel = fresnel_blocked / interior_pts

        # --- Clasificar estado con umbrales realistas ---
        # Se requiere bloqueo significativo para evitar falsos positivos
        if pct_los >= 0.40:
            fresnel_status   = "Bloqueo Severo"
            obstruction_loss = 30.0
        elif pct_los >= 0.15:
            fresnel_status   = "Bloqueo Severo"
            obstruction_loss = 20.0
        elif pct_los > 0.0 or pct_fresnel >= 0.40:
            fresnel_status   = "Obstruccion Parcial"
            obstruction_loss = 12.0
        elif pct_fresnel >= 0.15:
            fresnel_status   = "Obstruccion Leve"
            obstruction_loss = 4.0
        else:
            fresnel_status   = "Despejada"
            obstruction_loss = 0.0

        return profile, obstruction_loss, fresnel_status
