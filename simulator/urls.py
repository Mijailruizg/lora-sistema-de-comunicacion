from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/simulate/', views.simulate_api, name='simulate_api'),
    path('api/history/', views.history_api, name='history_api'),
    path('api/export-pdf/<int:sim_id>/', views.export_pdf, name='export_pdf'),
]
