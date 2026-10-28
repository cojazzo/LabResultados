-- Exporta el padrón de tamiz-escolar (ciclo 2026-2027) como JSON Lines para sync_padron_tamiz.py.
-- Ejecutar SOLO lectura contra la base `tamiz`:
--   docker exec -i tamiz-escolar-db-1 psql -U tamiz -d tamiz -t -A < export_padron_tamiz.sql > /tmp/padron_tamiz.jsonl
-- Nota: `sexo` sale con la convención de tamiz/CURP (H = hombre, M = mujer); el servicio la convierte.
SELECT json_build_object(
  'folio', trim(a.folio),
  'curp', NULLIF(trim(a.curp), ''),
  'nombres', trim(a.nombres),
  'primer_apellido', NULLIF(trim(a.primer_apellido), ''),
  'segundo_apellido', NULLIF(trim(a.segundo_apellido), ''),
  'fecha_nacimiento', a.fecha_nacimiento,
  'sexo', trim(a.sexo),
  'telefono', NULLIF(trim(a.telefono), ''),
  'provisional', a.provisional,
  'cct', trim(m.cct),
  'escuela', e.nombre,
  'subnivel', e.subnivel,
  'municipio', e.municipio,
  'localidad', e.localidad,
  'turno', m.turno,
  'grado', m.grado,
  'grupo', m.grupo,
  'zona_escolar', COALESCE(m.zona_escolar, e.zona_escolar),
  'ronda', c.numero,
  'fecha_evaluacion', ev.fecha,
  'peso_kg', ev.peso_kg,
  'talla_cm', ev.talla_cm
)
FROM alumno a
JOIN matricula m ON m.alumno_id = a.id AND m.activa AND m.ciclo_id = '2026-2027'
JOIN escuela e ON e.cct = m.cct
LEFT JOIN LATERAL (
  SELECT x.* FROM evaluacion x JOIN campana c0 ON c0.id = x.campana_id
  WHERE x.alumno_id = a.id AND c0.ciclo_id = '2026-2027'
  ORDER BY x.fecha DESC LIMIT 1
) ev ON true
LEFT JOIN campana c ON c.id = ev.campana_id
ORDER BY a.folio;
