#!/usr/bin/env python3
"""
Script para procesar datos de BigQuery y crear archivo optimizado para dashboard H3
"""

import json
import h3
from collections import defaultdict
from datetime import datetime
import sys

def process_delivery_data():
    print("🔄 Procesando datos de entregas...")
    
    try:
        # Cargar datos originales
        print("📂 Cargando densityexportv1.json...")
        with open('densityexportv1.json', 'r') as f:
            raw_data = json.load(f)
        
        print(f"✅ Cargados {len(raw_data):,} registros")
        
        # Configuración H3 - múltiples resoluciones
        H3_RESOLUTIONS = [6, 7, 8, 9, 10, 11, 12]
        
        # Procesar entregas individuales primero
        deliveries = []
        processed_count = 0
        valid_count = 0
        
        print("🗺️  Procesando coordenadas...")
        
        for i, record in enumerate(raw_data):
            if i % 50000 == 0:
                print(f"   Procesados {i:,}/{len(raw_data):,} ({i/len(raw_data)*100:.1f}%)")
            
            try:
                lat = float(record.get('SHP_LG_STOP_GPS_LATITUDE', 0))
                lng = float(record.get('SHP_LG_STOP_GPS_LONGITUDE', 0))
                
                # Filtrar coordenadas válidas (Argentina/CABA aproximado)
                if -40 <= lat <= -30 and -70 <= lng <= -50:
                    # Crear registro de entrega
                    delivery = {
                        'lat': lat,
                        'lng': lng,
                        'route_id': record.get('shp_lg_route_id'),
                        'stop_sequence': int(record.get('SHP_LG_STOP_SEQUENCE', 0)),
                        'date': record.get('shp_lg_init_date', '').split('T')[0],  # Solo fecha
                        'facility': record.get('SHP_LG_FACILITY_ID')
                    }
                    
                    deliveries.append(delivery)
                    valid_count += 1
                
                processed_count += 1
                
            except (ValueError, TypeError) as e:
                continue
        
        print(f"✅ Procesadas {valid_count:,} entregas válidas")
        
        # Agrupar por múltiples resoluciones H3
        print("🗺️  Agrupando por múltiples resoluciones H3...")
        resolutions_data = {}
        
        for resolution in H3_RESOLUTIONS:
            print(f"   Procesando resolución H3-{resolution}...")
            hexagon_data = defaultdict(list)
            
            for delivery in deliveries:
                h3_index = h3.latlng_to_cell(delivery['lat'], delivery['lng'], resolution)
                hexagon_data[h3_index].append(delivery)
            
            resolutions_data[resolution] = dict(hexagon_data)
            print(f"   H3-{resolution}: {len(hexagon_data):,} hexágonos")
        
        # Obtener fechas únicas para filtros
        all_dates = sorted(set(d['date'] for d in deliveries if d['date']))
        print(f"📅 Fechas disponibles: {all_dates[0]} a {all_dates[-1]} ({len(all_dates)} días)"
        
        print(f"✅ Procesamiento completo: {valid_count:,} entregas válidas de {processed_count:,} registros")
        
        # Crear archivo optimizado multi-resolución
        optimized_data = {
            'metadata': {
                'total_deliveries': valid_count,
                'available_dates': all_dates,
                'date_range': {
                    'start': all_dates[0] if all_dates else None,
                    'end': all_dates[-1] if all_dates else None
                },
                'h3_resolutions': H3_RESOLUTIONS,
                'processed_at': datetime.now().isoformat(),
                'source_records': len(raw_data)
            },
            'resolutions': {}
        }
        
        print("📈 Calculando métricas por resolución...")
        
        for resolution in H3_RESOLUTIONS:
            print(f"   Procesando métricas H3-{resolution}...")
            hexagon_data = resolutions_data[resolution]
            resolution_hexagons = {}
            
            for h3_index, hex_deliveries in hexagon_data.items():
                # Calcular estadísticas del hexágono
                unique_routes = len(set(d['route_id'] for d in hex_deliveries if d['route_id']))
                
                # Obtener fechas únicas
                dates = list(set(d['date'] for d in hex_deliveries if d['date']))
                
                # Centro del hexágono para referencia
                center_lat, center_lng = h3.cell_to_latlng(h3_index)
                
                # Agrupar entregas por fecha para filtrado
                deliveries_by_date = defaultdict(list)
                for delivery in hex_deliveries:
                    if delivery['date']:
                        deliveries_by_date[delivery['date']].append(delivery)
                
                resolution_hexagons[h3_index] = {
                    'center_lat': center_lat,
                    'center_lng': center_lng,
                    'delivery_count': len(hex_deliveries),
                    'unique_routes': unique_routes,
                    'date_range': {
                        'start': min(dates) if dates else None,
                        'end': max(dates) if dates else None
                    },
                    'deliveries_by_date': dict(deliveries_by_date),
                    'sample_deliveries': hex_deliveries[:3]  # Muestra más pequeña
                }
            
            optimized_data['resolutions'][resolution] = {
                'hexagon_count': len(resolution_hexagons),
                'hexagons': resolution_hexagons
            }
        
        # Guardar archivo optimizado
        output_file = 'density_data_multi_res.json'
        print(f"💾 Guardando archivo multi-resolución: {output_file}")
        
        with open(output_file, 'w') as f:
            json.dump(optimized_data, f, indent=2)
        
        # Mostrar estadísticas del archivo
        import os
        original_size = os.path.getsize('densityexportv1.json') / (1024 * 1024)
        optimized_size = os.path.getsize(output_file) / (1024 * 1024)
        
        print(f"\n📊 Resumen:")
        print(f"   Archivo original: {original_size:.1f} MB")
        print(f"   Archivo multi-resolución: {optimized_size:.1f} MB")
        print(f"   Resoluciones H3: {len(H3_RESOLUTIONS)} ({min(H3_RESOLUTIONS)}-{max(H3_RESOLUTIONS)})")
        print(f"   Entregas válidas: {valid_count:,}")
        print(f"   Fechas disponibles: {len(all_dates)} días")
        print(f"   Período: {all_dates[0]} a {all_dates[-1]}")
        
        # Mostrar estadísticas por resolución
        print(f"\n📐 Hexágonos por resolución:")
        for resolution in H3_RESOLUTIONS:
            count = optimized_data['resolutions'][resolution]['hexagon_count']
            print(f"   H3-{resolution}: {count:,} hexágonos")
        
        return True
        
    except Exception as e:
        print(f"❌ Error procesando datos: {e}")
        return False

if __name__ == "__main__":
    success = process_delivery_data()
    sys.exit(0 if success else 1)