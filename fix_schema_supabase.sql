-- Script para corregir el esquema de la base de datos en Supabase
-- Ejecutar este script en el SQL Editor de Supabase

-- Deshabilitar RLS temporalmente
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE poker_results DISABLE ROW LEVEL SECURITY;

-- Eliminar la tabla poker_results si existe (para recrearla)
DROP TABLE IF EXISTS poker_results CASCADE;

-- Recrear la tabla poker_results con el esquema correcto
CREATE TABLE poker_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fecha DATE NOT NULL,
    hora TIME,
    descripcion TEXT NOT NULL,
    importe DECIMAL(10,2) NOT NULL,
    categoria VARCHAR(50) NOT NULL,
    tipo_movimiento VARCHAR(50) NOT NULL,
    tipo_juego VARCHAR(50) NOT NULL,
    sala VARCHAR(50) NOT NULL,
    nivel_buyin VARCHAR(20),
    hash_duplicado VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear índices para mejorar rendimiento
CREATE INDEX idx_poker_results_user_id ON poker_results(user_id);
CREATE INDEX idx_poker_results_fecha ON poker_results(fecha);
CREATE INDEX idx_poker_results_categoria ON poker_results(categoria);
CREATE INDEX idx_poker_results_sala ON poker_results(sala);
CREATE INDEX idx_poker_results_hash_duplicado ON poker_results(hash_duplicado);
CREATE INDEX idx_poker_results_user_fecha ON poker_results(user_id, fecha);

-- Habilitar RLS nuevamente
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE poker_results ENABLE ROW LEVEL SECURITY;

-- Crear políticas RLS simplificadas
CREATE POLICY "Users can view own data" ON poker_results FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can insert own data" ON poker_results FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users can update own data" ON poker_results FOR UPDATE USING (user_id = auth.uid());
CREATE POLICY "Users can delete own data" ON poker_results FOR DELETE USING (user_id = auth.uid());

-- Verificar que la tabla se creó correctamente
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'poker_results' 
ORDER BY ordinal_position;
