document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Map
    const map = L.map('map', {
        attributionControl: false // Elimina "Leaflet | © OSM contributors"
    }).setView([-16.0964, -61.2158], 12); // Centrado en el punto del ejercicio

    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
    }).addTo(map);

    let txMarker = null;
    let rxMarker = null;
    let linkLine = null;
    let coverageCircle = null;
    let prxChart = null;
    let elevationChart = null;
    let locations = JSON.parse(localStorage.getItem('lora_locations') || '[]');

    const txIcon = L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
        iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41]
    });

    const rxIcon = L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
        iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41]
    });

    // 2. Map click logic
    map.on('click', async (e) => {
        const txDisplay = document.getElementById('loc-tx-display');
        const rxDisplay = document.getElementById('loc-rx-display');
        const hintEl = document.getElementById('map-status-hint');

        if (!txMarker) {
            txMarker = L.marker(e.latlng, { icon: txIcon }).addTo(map).bindPopup("Transmisor (TX)").openPopup();
            txDisplay.innerHTML = `<i class="fa-solid fa-circle-check text-success me-1"></i> ${e.latlng.lat.toFixed(6)}, ${e.latlng.lng.toFixed(6)}`;
            txDisplay.classList.add('placed');
            hintEl.innerHTML = '<i class="fa-solid fa-hand-pointer me-1"></i>Clic para colocar RX';
            // Detectar entorno automaticamente al colocar TX
            detectEnvironment(e.latlng.lat, e.latlng.lng);
        } else if (!rxMarker) {
            rxMarker = L.marker(e.latlng, { icon: rxIcon }).addTo(map).bindPopup("Receptor (RX)").openPopup();
            rxDisplay.innerHTML = `<i class="fa-solid fa-circle-check text-orange me-1"></i> ${e.latlng.lat.toFixed(6)}, ${e.latlng.lng.toFixed(6)}`;
            rxDisplay.classList.add('placed-rx');
            hintEl.innerHTML = '<i class="fa-solid fa-check-circle text-success me-1"></i>Puntos listos';
            document.getElementById('btn-simulate').disabled = false;
            updateSaveButton();
        } else {
            // move rx marker if already 2 points
            rxMarker.setLatLng(e.latlng);
            rxDisplay.innerHTML = `<i class="fa-solid fa-circle-check text-orange me-1"></i> ${e.latlng.lat.toFixed(6)}, ${e.latlng.lng.toFixed(6)}`;
            if (linkLine) { map.removeLayer(linkLine); linkLine = null; }
            if (coverageCircle) { map.removeLayer(coverageCircle); coverageCircle = null; }
            document.getElementById('results-card').classList.add('d-none');
            updateSaveButton();
        }
    });

    // Deteccion automatica de entorno via Nominatim + heuristicas OSM
    async function detectEnvironment(lat, lng) {
        const loadingEl = document.getElementById('env-loading');
        const hintEl = document.getElementById('env-hint');
        const envSelect = document.getElementById('environment');
        const envBox = document.getElementById('env-box');

        loadingEl.classList.remove('d-none');
        hintEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analizando entorno...';
        envBox.style.background = '#f0f4ff';

        try {
            // 1) Nominatim: reverse geocoding para obtener tipo de zona
            const nomUrl = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&addressdetails=1&zoom=16`;
            const nomRes = await fetch(nomUrl, { headers: { 'Accept-Language': 'es' } });
            const nomData = await nomRes.json();

            const addr = nomData.address || {};
            const displayName = nomData.display_name || 'Zona desconocida';

            // 2) Overpass API: consultas SEPARADAS para clasificar con precision
            const overpassUrl = 'https://overpass-api.de/api/interpreter';
            const radius = 500;

            // Consulta de edificios (urbano)
            const qBuildings = `[out:json][timeout:10];(way["building"](around:${radius},${lat},${lng}); way["landuse"~"residential|commercial|industrial"](around:${radius},${lat},${lng}); way["highway"~"motorway|primary|secondary"](around:${radius},${lat},${lng}););out count;`;
            // Consulta de vegetacion/bosque
            const qForest = `[out:json][timeout:10];(way["landuse"~"forest|wood|nature_reserve|scrub"](around:${radius},${lat},${lng}); relation["natural"~"wood|grassland"](around:${radius},${lat},${lng}););out count;`;

            const [bRes, fRes] = await Promise.all([
                fetch(overpassUrl, { method: 'POST', body: `data=${encodeURIComponent(qBuildings)}` }),
                fetch(overpassUrl, { method: 'POST', body: `data=${encodeURIComponent(qForest)}` })
            ]);
            const [bData, fData] = await Promise.all([bRes.json(), fRes.json()]);

            const buildingCount = bData.elements ? parseInt(bData.elements[0]?.tags?.total || 0) : 0;
            const forestCount = fData.elements ? parseInt(fData.elements[0]?.tags?.total || 0) : 0;

            // 3) Clasificacion heuristica con prioridad
            let env = 'Rural';
            let envLabel = 'Rural';

            // Prioridad: bosque > urbano > suburbano > rural
            const isCity = addr.city || addr.town;
            const isVillage = addr.village;
            const isSuburb = addr.suburb || addr.quarter;

            if (forestCount >= 1) {
                env = 'Bosque';
                envLabel = 'Bosque';
            } else if (buildingCount > 30 || (isCity && !isVillage)) {
                env = 'Urbano';
                envLabel = 'Urbano';
            } else if (buildingCount > 8 || isSuburb || isVillage) {
                env = 'Suburbano';
                envLabel = 'Suburbano';
            } else {
                env = 'Rural';
                envLabel = 'Rural';
            }

            // Aplicar al selector
            envSelect.value = env;

            // Mostrar resultado con estadisticas
            const shortName = displayName.split(',').slice(0, 3).join(', ');
            const detail = env === 'Bosque'
                ? `${forestCount} zona(s) de vegetacion detectadas en 500m`
                : env === 'Urbano'
                    ? `${buildingCount} elementos urbanos detectados en 500m`
                    : env === 'Suburbano'
                        ? `${buildingCount} construcciones detectadas en 500m`
                        : 'Zona abierta sin edificios significativos';

            hintEl.innerHTML = `<i class="fa-solid fa-location-dot text-success me-1"></i><strong>${envLabel}</strong> &mdash; ${shortName}<br><small class="text-muted">${detail}</small>`;

            const bgColors = { 'Urbano': '#fff8f0', 'Bosque': '#f0faf0', 'Suburbano': '#f8f0ff', 'Rural': '#f0f8f0' };
            envBox.className = 'mb-2 env-rural';  // reset
            envBox.style.background = bgColors[env] || '#f7fafd';
            envBox.style.borderColor = env === 'Urbano' ? '#d5b87a' : env === 'Bosque' ? '#6dae6d' : env === 'Suburbano' ? '#c8a8d5' : '#a8d5a8';

        } catch (err) {
            hintEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation text-warning"></i> No se pudo detectar. Selecciona manualmente.';
        } finally {
            loadingEl.classList.add('d-none');
        }
    }

    // 3. Reset Button
    document.getElementById('btn-reset').addEventListener('click', () => {
        if (txMarker) map.removeLayer(txMarker);
        if (rxMarker) map.removeLayer(rxMarker);
        if (linkLine) map.removeLayer(linkLine);
        if (coverageCircle) map.removeLayer(coverageCircle);
        if (prxChart) { prxChart.destroy(); prxChart = null; }
        if (elevationChart) { elevationChart.destroy(); elevationChart = null; }
        txMarker = null;
        rxMarker = null;
        linkLine = null;
        coverageCircle = null;
        document.getElementById('btn-simulate').disabled = true;
        document.getElementById('results-card').classList.add('d-none');
        document.getElementById('elevation-card').classList.add('d-none');
        document.getElementById('btn-export-pdf').classList.add('d-none');

        // Reset location UI
        document.getElementById('loc-tx-display').innerHTML = '<i class="fa-solid fa-circle-xmark text-secondary me-1"></i>Sin seleccionar';
        document.getElementById('loc-rx-display').innerHTML = '<i class="fa-solid fa-circle-xmark text-secondary me-1"></i>Sin seleccionar';
        document.getElementById('loc-tx-display').className = 'coord-point-box';
        document.getElementById('loc-rx-display').className = 'coord-point-box';
        document.getElementById('map-status-hint').innerHTML = '<i class="fa-solid fa-hand-pointer me-1"></i>Clic para colocar TX';
        document.getElementById('btn-save-loc').disabled = true;
    });

    // Preset de frecuencia: al elegir en la lista, actualiza el input numérico y el BW
    document.getElementById('freq-preset').addEventListener('change', (e) => {
        const opt = e.target.selectedOptions[0];
        const val = e.target.value;
        const freqInput = document.getElementById('frequency');
        const bwSelect = document.getElementById('bw_hz');
        const hintEl = document.getElementById('freq-hint');

        if (val !== 'custom') {
            freqInput.value = val;
            // Ajustar BW sugerido
            const suggestedBw = opt.dataset.bw;
            if (suggestedBw) bwSelect.value = suggestedBw;
        }

        // Actualizar hint informativo
        const hints = {
            '433': 'Alta penetración en materiales. Mayor interferencia. Alcance: 10–20 km en campo abierto.',
            '470': 'Banda China (CN470). Alta penetración. Uso en Asia y algunos despliegues LATAM.',
            '868': 'Frecuencia oficial LoRaWAN Europa. Balance óptimo. Alcance: 5–15 km.',
            '915': 'Frecuencia oficial LoRaWAN América/LATAM. Balance estándar. Alcance: 5–15 km.',
            '923': 'Banda AS923 para Asia-Pacífico. Alta penetración en zonas dense.',
            '2400': 'LoRa 2.4 GHz. Mayor capacidad, menor alcance. Sensible a obstáculos. Alcance: 1–5 km.',
            'custom': 'Ingresa la frecuencia deseada en el campo numérico.'
        };
        hintEl.innerHTML = `<i class="fa-solid fa-circle-info"></i> ${hints[val] || hints['915']}`;
    });

    // Cambios en el input de frecuencia manual
    document.getElementById('frequency').addEventListener('input', () => {
        document.getElementById('freq-preset').value = 'custom';
        document.getElementById('freq-hint').innerHTML = '<i class="fa-solid fa-pen"></i> Frecuencia personalizada.';
    });

    // 4. Simulate Button
    document.getElementById('btn-simulate').addEventListener('click', async () => {
        if (!txMarker || !rxMarker) return;

        const data = {
            tx_lat: txMarker.getLatLng().lat,
            tx_lng: txMarker.getLatLng().lng,
            rx_lat: rxMarker.getLatLng().lat,
            rx_lng: rxMarker.getLatLng().lng,
            frequency_mhz: parseFloat(document.getElementById('frequency').value),
            tx_power_dbm: parseFloat(document.getElementById('tx_power').value),
            tx_gain_dbi: parseFloat(document.getElementById('tx_gain').value),
            rx_gain_dbi: parseFloat(document.getElementById('rx_gain').value),
            tx_cable_loss: parseFloat(document.getElementById('cable_loss').value) / 2, // Assuming split equally or just sending half
            rx_cable_loss: parseFloat(document.getElementById('cable_loss').value) / 2,
            environment: document.getElementById('environment').value,
            ant_height_tx: parseFloat(document.getElementById('ant_height_tx').value) || 15,
            ant_height_rx: parseFloat(document.getElementById('ant_height_rx').value) || 3,
            sf: parseInt(document.getElementById('sf').value),
            bw_hz: parseInt(document.getElementById('bw_hz').value)
        };

        try {
            const response = await fetch('/api/simulate/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const resData = await response.json();

            if (resData.status === 'success') {
                updateUI(resData.results);
                drawLinkLine(resData.results);
                drawChart(resData.results, resData.results.sensitivity_dbm);
                drawElevationChart(resData.results.elevation_profile, resData.results.fresnel_status);

                // Show export button
                const btnExport = document.getElementById('btn-export-pdf');
                btnExport.href = `/api/export-pdf/${resData.id}/`;
                btnExport.classList.remove('d-none');

                loadHistory();
            } else {
                alert("Error en la simulación: " + resData.message);
            }
        } catch (err) {
            console.error(err);
            alert("Error de conexión con el servidor.");
        }
    });

    function updateUI(results) {
        document.getElementById('results-card').classList.remove('d-none');
        document.getElementById('res-distance').innerText = results.distance_km.toFixed(2) + " km";
        document.getElementById('res-fspl').innerText = (results.fspl_db + results.obstruction_loss_db).toFixed(2) + " dB";
        document.getElementById('res-prx').innerText = results.rx_power_dbm.toFixed(2) + " dBm";

        const fresnelBadge = document.getElementById('res-fresnel-badge');
        const fresnelTxt = results.fresnel_status;
        fresnelBadge.innerText = "Fresnel: " + fresnelTxt;
        const fresnelClass = fresnelTxt === 'Despejada'
            ? 'bg-success'
            : fresnelTxt === 'Obstruccion Leve'
                ? 'bg-info text-dark'
                : fresnelTxt.includes('Parcial')
                    ? 'bg-warning text-dark'
                    : 'bg-danger';  // Bloqueo Severo
        fresnelBadge.className = 'badge fs-6 ' + fresnelClass;

        const statusEl = document.getElementById('res-status');
        const marginEl = document.getElementById('res-margin');
        const marginDb = results.rx_power_dbm - results.sensitivity_dbm;

        marginEl.innerText = `Sensibilidad: ${results.sensitivity_dbm.toFixed(2)} dBm | Margen: ${marginDb.toFixed(2)} dB`;

        const statusBox = document.getElementById('res-status-box');

        if (results.link_ok) {
            statusEl.innerText = "ENLACE VIABLE (OK)";
            statusEl.className = "text-success fw-bold";
            statusBox.style.backgroundColor = "#e8f5e9";
        } else {
            statusEl.innerText = "SIN COBERTURA (FAIL)";
            statusEl.className = "text-danger fw-bold";
            statusBox.style.backgroundColor = "#ffebee";
        }

        // Panel Entorno Detectado
        const envLosses = { 'Urbano': 35, 'Bosque': 25, 'Suburbano': 20, 'Rural': 15 };
        const envDescMap = {
            'Urbano': 'Atenuacion por edificios y reflexiones multiples (+35 dB)',
            'Bosque': 'Atenuacion por absorcion de vegetacion densa (+25 dB)',
            'Suburbano': 'Atenuacion moderada por vegetacion y construccion (+20 dB)',
            'Rural': 'Atenuacion minima, campo abierto o terreno despejado (+15 dB)'
        };
        const env = results.environment || document.getElementById('environment').value;
        const envLoss = envLosses[env] || 15;
        const totalLoss = results.fspl_db + results.obstruction_loss_db + envLoss;

        document.getElementById('res-env-type').innerText = env;
        document.getElementById('res-env-loss').innerText = `+${envLoss} dB`;
        document.getElementById('res-env-total').innerText = `${totalLoss.toFixed(1)} dB`;
        document.getElementById('res-env-desc').innerText = envDescMap[env] || '';
    }

    function drawLinkLine(results) {
        if (linkLine) map.removeLayer(linkLine);
        if (coverageCircle) map.removeLayer(coverageCircle);

        const latlngs = [txMarker.getLatLng(), rxMarker.getLatLng()];
        const color = results.link_ok ? '#28a745' : '#dc3545'; // Green or Red

        // Draw tooltip
        const tooltipText = `Distancia: ${results.distance_km.toFixed(2)} km<br>Señal: ${results.rx_power_dbm.toFixed(2)} dBm`;

        // Límite práctico de despliegue basado en condiciones reales
        const maxRanges = {
            433: 20000,
            470: 18000,
            868: 15000,
            915: 15000,
            923: 14000,
            2400: 5000
        };
        const freq = parseFloat(document.getElementById('frequency').value);
        const limitRangeMeters = maxRanges[freq] || 15000;
        let radiusMeters = results.max_range_km * 1000;
        let coverageWarning = "";

        if (radiusMeters > limitRangeMeters) {
            radiusMeters = limitRangeMeters;
            coverageWarning = "<br><span class='text-warning small'>⚠️ Cobertura teórica excede límites prácticos</span>";
        }

        linkLine = L.polyline(latlngs, { color: color, weight: 4, opacity: 0.8, dashArray: '10, 10' })
            .bindTooltip(tooltipText + coverageWarning, { permanent: false, sticky: true })
            .addTo(map);

        // Draw Coverage Circle
        coverageCircle = L.circle(txMarker.getLatLng(), {
            color: '#17a2b8',
            fillColor: '#17a2b8',
            fillOpacity: 0.1,
            radius: radiusMeters // meters
        }).addTo(map);

        // Fit bounds to include both points and maybe circle
        const group = new L.featureGroup([txMarker, rxMarker]);
        map.fitBounds(group.getBounds(), { padding: [50, 50] });
    }

    function drawChart(results, sensitivity) {
        const ctx = document.getElementById('prxChart').getContext('2d');
        if (prxChart) {
            prxChart.destroy();
        }

        // We'll just plot 3 points: TX (0km), RX (distance_km), Limit (max_range_km)
        // A real curve could be generated, but a simple 3-point or simple line is enough for 'simple chart'

        prxChart = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [
                    {
                        label: 'Nivel Rx (dBm)',
                        data: [
                            { x: results.distance_km, y: results.rx_power_dbm }
                        ],
                        backgroundColor: results.link_ok ? '#28a745' : '#dc3545',
                        pointRadius: 8
                    },
                    {
                        label: 'Sensibilidad (Límite)',
                        data: [
                            { x: 0, y: sensitivity },
                            { x: Math.max(results.distance_km, results.max_range_km) * 1.2, y: sensitivity }
                        ],
                        type: 'line',
                        borderColor: '#ffc107',
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        title: { display: true, text: 'Distancia (km)' },
                        min: 0
                    },
                    y: {
                        title: { display: true, text: 'Potencia (dBm)' },
                        suggestedMax: -40,
                        suggestedMin: sensitivity - 10
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.parsed.x.toFixed(2)} km, ${ctx.parsed.y.toFixed(2)} dBm`
                        }
                    }
                }
            }
        });
    }

    function drawElevationChart(profile, fresnelStatus) {
        document.getElementById('elevation-card').classList.remove('d-none');
        const ctx = document.getElementById('elevationChart').getContext('2d');
        if (elevationChart) {
            elevationChart.destroy();
        }

        const labels = profile.map(p => p.distance.toFixed(2) + ' km');
        const elevations = profile.map(p => p.elevation);
        const los = profile.map(p => p.los_elevation);
        
        // 1. & 2. Calcular los límites de la primera zona de Fresnel (100%)
        const fresnelUpper = profile.map(p => p.los_elevation + p.fresnel_radius);
        const fresnelLower = profile.map(p => p.los_elevation - p.fresnel_radius);

        const minElev = Math.min(...elevations, ...fresnelLower);
        const maxElev = Math.max(...elevations, ...los, ...fresnelUpper);
        const padding = Math.max((maxElev - minElev) * 0.2, 20);

        // 7. Detectar obstrucciones y marcar visualmente cambiando el color de la elipse
        let fresnelFill = 'rgba(40, 167, 69, 0.2)'; // Verde (Despejada)
        let fresnelBorder = 'rgba(40, 167, 69, 0.5)';
        
        if (fresnelStatus && fresnelStatus.includes("Severo")) {
            fresnelFill = 'rgba(220, 53, 69, 0.2)'; // Rojo (Obstrucción Severa)
            fresnelBorder = 'rgba(220, 53, 69, 0.5)';
        } else if (fresnelStatus && (fresnelStatus.includes("Parcial") || fresnelStatus.includes("Leve"))) {
            fresnelFill = 'rgba(255, 193, 7, 0.2)'; // Amarillo (Obstrucción Parcial/Leve)
            fresnelBorder = 'rgba(255, 193, 7, 0.5)';
        }

        elevationChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Perfil Topográfico',
                        data: elevations,
                        fill: true,
                        backgroundColor: 'rgba(139, 69, 19, 0.4)', // Brownish terrain
                        borderColor: 'rgba(139, 69, 19, 1)',
                        pointRadius: 0,
                        tension: 0.2,
                        order: 2
                    },
                    {
                        label: 'Línea de Vista (LOS)',
                        data: los,
                        fill: false,
                        borderColor: '#28a745', // Green
                        borderDash: [5, 5],
                        pointRadius: 0,
                        order: 1
                    },
                    {
                        label: '1ra Zona Fresnel Sup',
                        data: fresnelUpper,
                        fill: false,
                        borderColor: fresnelBorder,
                        borderDash: [2, 2],
                        pointRadius: 0,
                        order: 3
                    },
                    {
                        label: '1ra Zona Fresnel Inf',
                        data: fresnelLower,
                        fill: '-1', // Rellena el área hacia la curva superior
                        backgroundColor: fresnelFill,
                        borderColor: fresnelBorder,
                        borderDash: [2, 2],
                        pointRadius: 0,
                        order: 4
                    }
                ]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        ticks: { maxTicksLimit: 10 }
                    },
                    y: {
                        title: { display: true, text: 'Elevación (m s.n.m.)' },
                        min: Math.floor(Math.max(0, minElev - padding)),
                        max: Math.ceil(maxElev + padding)
                    }
                },
                plugins: {
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                }
            }
        });
    }

    async function loadHistory() {
        try {
            const response = await fetch('/api/history/');
            const data = await response.json();
            if (data.status === 'success') {
                const list = document.getElementById('history-list');
                list.innerHTML = '';
                data.history.forEach(item => {
                    const icon = item.link_ok ? '<i class="fa-solid fa-check text-success"></i>' : '<i class="fa-solid fa-xmark text-danger"></i>';
                    const li = document.createElement('li');
                    li.className = 'list-group-item small';
                    li.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center">
                            <span>${icon} ${item.frequency_mhz}MHz (${item.distance_km}km)</span>
                            <strong>${item.rx_power_dbm} dBm</strong>
                        </div>
                    `;
                    list.appendChild(li);
                });
            }
        } catch (err) {
            console.error("Error cargando historial", err);
        }
    }

    // 5. Presentation Mode Exercise
    window.loadExercise = async function () {
        const lat = -16.09648999;
        const lng = -61.21581227;
        const latlng = L.latLng(lat, lng);

        // Reset previous
        document.getElementById('btn-reset').click();

        // Place TX
        txMarker = L.marker(latlng, { icon: txIcon }).addTo(map).bindPopup("Transmisor (TX) - Ejercicio").openPopup();
        await detectEnvironment(lat, lng);

        // Place RX (offset slightly for simulation, approx 5km)
        const rxLatlng = L.latLng(lat + 0.03, lng + 0.03);
        rxMarker = L.marker(rxLatlng, { icon: rxIcon }).addTo(map).bindPopup("Receptor (RX) - Ejercicio").openPopup();

        document.getElementById('btn-simulate').disabled = false;
        map.setView(latlng, 13);

        // Auto-scroll to sidebar
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // 6. Location Management Logic
    function updateSaveButton() {
        const name = document.getElementById('loc-name').value.trim();
        document.getElementById('btn-save-loc').disabled = !(txMarker && rxMarker && name);
    }

    document.getElementById('loc-name').addEventListener('input', updateSaveButton);

    document.getElementById('btn-save-loc').addEventListener('click', () => {
        if (!txMarker || !rxMarker) return;
        const name = document.getElementById('loc-name').value.trim();
        if (!name) return;

        const newLoc = {
            name: name,
            tx: txMarker.getLatLng(),
            rx: rxMarker.getLatLng(),
            environment: document.getElementById('environment').value,
            timestamp: new Date().getTime()
        };

        locations.push(newLoc);
        localStorage.setItem('lora_locations', JSON.stringify(locations));

        // Reset UI
        document.getElementById('loc-name').value = '';
        renderLocations();
        alert('Ubicación guardada con éxito.');
    });

    function renderLocations() {
        const list = document.getElementById('loc-list');
        const emptyHint = document.getElementById('loc-empty');
        const countBadge = document.getElementById('loc-count-badge');

        list.innerHTML = '';
        countBadge.innerText = locations.length;

        if (locations.length === 0) {
            emptyHint.classList.remove('d-none');
            return;
        }

        emptyHint.classList.add('d-none');

        locations.forEach((loc, index) => {
            const li = document.createElement('li');
            li.className = 'loc-item';
            li.innerHTML = `
                <div class="d-flex justify-content-between align-items-start mb-1">
                    <span class="loc-name text-truncate" style="max-width: 150px;">${loc.name}</span>
                    <button class="btn btn-link btn-sm text-danger p-0" onclick="deleteLocation(${index})">
                        <i class="fa-solid fa-trash-can" style="font-size: 0.65rem;"></i>
                    </button>
                </div>
                <div class="d-flex gap-1 mb-2">
                    <span class="coord-badge">TX: ${loc.tx.lat.toFixed(4)}, ${loc.tx.lng.toFixed(4)}</span>
                    <span class="coord-badge rx">RX: ${loc.rx.lat.toFixed(4)}, ${loc.rx.lng.toFixed(4)}</span>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-outline-primary btn-xs w-50 py-0" style="font-size: 0.65rem;" onclick="loadLocation(${index})">
                        <i class="fa-solid fa-eye me-1"></i>Cargar
                    </button>
                    <button class="btn btn-primary btn-xs w-50 py-0" style="font-size: 0.65rem;" onclick="simulateLocation(${index})">
                        <i class="fa-solid fa-play me-1"></i>Simular
                    </button>
                </div>
            `;
            list.appendChild(li);
        });
    }

    window.deleteLocation = function (index) {
        if (confirm('¿Eliminar esta ubicación?')) {
            locations.splice(index, 1);
            localStorage.setItem('lora_locations', JSON.stringify(locations));
            renderLocations();
        }
    };

    window.loadLocation = async function (index) {
        const loc = locations[index];

        // Reset current
        document.getElementById('btn-reset').click();

        // Set name to input
        document.getElementById('loc-name').value = loc.name;

        // Place TX
        const txLatLng = L.latLng(loc.tx.lat, loc.tx.lng);
        txMarker = L.marker(txLatLng, { icon: txIcon }).addTo(map).bindPopup(`<b>${loc.name}</b><br>Transmisor (TX)`).openPopup();

        const txDisplay = document.getElementById('loc-tx-display');
        txDisplay.innerHTML = `<i class="fa-solid fa-circle-check text-success me-1"></i> ${txLatLng.lat.toFixed(6)}, ${txLatLng.lng.toFixed(6)}`;
        txDisplay.classList.add('placed');

        // Detect environment
        await detectEnvironment(txLatLng.lat, txLatLng.lng);
        if (loc.environment) document.getElementById('environment').value = loc.environment;

        // Place RX
        const rxLatLng = L.latLng(loc.rx.lat, loc.rx.lng);
        rxMarker = L.marker(rxLatLng, { icon: rxIcon }).addTo(map).bindPopup("Receptor (RX)").openPopup();

        const rxDisplay = document.getElementById('loc-rx-display');
        rxDisplay.innerHTML = `<i class="fa-solid fa-circle-check text-orange me-1"></i> ${rxLatLng.lat.toFixed(6)}, ${rxLatLng.lng.toFixed(6)}`;
        rxDisplay.classList.add('placed-rx');

        document.getElementById('btn-simulate').disabled = false;
        document.getElementById('map-status-hint').innerHTML = '<i class="fa-solid fa-check-circle text-success me-1"></i>Ubicación cargada';

        // Fit bounds
        const group = new L.featureGroup([txMarker, rxMarker]);
        map.fitBounds(group.getBounds(), { padding: [50, 50] });

        updateSaveButton();
    };

    window.simulateLocation = async function (index) {
        await loadLocation(index);
        document.getElementById('btn-simulate').click();
    };

    // Load initial locations
    renderLocations();
    loadHistory();
});
