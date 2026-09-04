# Nominatim local

Geocodificador OpenStreetMap propio, para no depender de servicios públicos
(Nominatim/Photon públicos bloquean la IP del servidor en uso masivo).

- **Servicio:** `nominatim` en `docker-compose.yml` (raíz del repo).
- **Cobertura de datos:** estado de Aguascalientes + un buffer
  (bbox `-103.3,21.2,-101.4,22.9`, incluye bordes de Jalisco y Zacatecas).
- **Volumen:** `nominatim_db` (gestionado por compose → `labresultados_nominatim_db`).
  Contiene la BD ya importada; el contenedor sólo arranca PostgreSQL + API.
- **Consumo:** el backend lo llama en `http://nominatim:8080` desde
  `app/services/geocoding.py`, con fallback a Google.

## Operación normal

```bash
docker compose up -d nominatim
docker compose logs -f nominatim
curl http://localhost:8080/status      # "OK" cuando está listo (~15-30s)
```

Recursos: `shm_size 512m`, `mem_limit 2g`. La BD pesa ~240 MB.

## Reconstruir la base (ampliar cobertura o actualizar OSM)

Sólo si hace falta cambiar la zona o refrescar los datos. Necesitas el PBF de
México (~620 MB) y `osmium-tool`.

```bash
# 1. Descargar México y recortar la zona deseada
mkdir -p /tmp/nominatim-build && cd /tmp/nominatim-build
wget -O mexico.osm.pbf https://download.geofabrik.de/north-america/mexico-latest.osm.pbf
osmium extract -b -103.3,21.2,-101.4,22.9 mexico.osm.pbf -o aguascalientes.osm.pbf -s smart

# 2. Import en un contenedor temporal a un volumen NUEVO
docker volume create nominatim_rebuild
docker run -i --rm --shm-size=1g \
  -e PBF_PATH=/data/aguascalientes.osm.pbf \
  -e IMPORT_STYLE=address -e FREEZE=true \
  -e NOMINATIM_PASSWORD=nominatim_local_ags -e THREADS=4 \
  -v /tmp/nominatim-build:/data \
  -v nominatim_rebuild:/var/lib/postgresql/16/main \
  mediagis/nominatim:4.5

# 3. Cuando termine, cambiar el stack al volumen nuevo:
docker compose stop nominatim
docker run --rm -v nominatim_rebuild:/from:ro -v labresultados_nominatim_db:/to \
  alpine sh -c 'rm -rf /to/* && cp -a /from/. /to/'
docker volume rm nominatim_rebuild
docker compose up -d nominatim
```

**IMPORTANTE:** nunca montar un volumen en `/nominatim/flatnode` para un
extracto regional: osm2pgsql preasigna un flatnode de ~113 GB (indexado por el
ID máximo de nodo de OSM, ~14e9) y llena el disco.

## Rollback del geocoder

El backend cae a Google si Nominatim no responde. Para volver al geocoder
anterior (Photon): `git revert` del commit de esta feature y `docker compose up
-d --build backend`.
