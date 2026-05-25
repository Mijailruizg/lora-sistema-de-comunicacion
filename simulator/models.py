from django.db import models
from django.contrib.auth.models import User

class SimulationResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Parámetros de Entrada
    tx_lat = models.FloatField()
    tx_lng = models.FloatField()
    rx_lat = models.FloatField()
    rx_lng = models.FloatField()
    
    frequency_mhz = models.FloatField()
    tx_power_dbm = models.FloatField()
    tx_gain_dbi = models.FloatField()
    rx_gain_dbi = models.FloatField()
    tx_cable_loss = models.FloatField(default=0.0)
    rx_cable_loss = models.FloatField(default=0.0)
    environment = models.CharField(max_length=50, default='Rural')
    sf = models.IntegerField(default=7)
    bw_hz = models.IntegerField(default=125000)
    
    # Resultados Calculados
    distance_km = models.FloatField()
    fspl_db = models.FloatField()
    obstruction_loss_db = models.FloatField(default=0.0)
    fresnel_status = models.CharField(max_length=50, default="OK")
    rx_power_dbm = models.FloatField()
    link_ok = models.BooleanField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        status = "OK" if self.link_ok else "FAIL"
        return f"{self.frequency_mhz}MHz: {self.rx_power_dbm:.2f}dBm ({status})"

