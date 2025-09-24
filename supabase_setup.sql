-- Script de configuración para Supabase
-- Ejecutar este script en el SQL Editor de Supabase

-- Crear tabla de usuarios
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Crear tabla de resultados de poker
CREATE TABLE IF NOT EXISTS poker_results (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fecha DATE NOT NULL,
    hora TIME,
    descripcion VARCHAR(500) NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_poker_results_user_fecha ON poker_results(user_id, fecha);
CREATE INDEX IF NOT EXISTS idx_poker_results_user_categoria ON poker_results(user_id, categoria);
CREATE INDEX IF NOT EXISTS idx_poker_results_user_sala ON poker_results(user_id, sala);
CREATE INDEX IF NOT EXISTS idx_poker_results_hash_duplicado ON poker_results(hash_duplicado);
CREATE INDEX IF NOT EXISTS idx_poker_results_fecha ON poker_results(fecha);
CREATE INDEX IF NOT EXISTS idx_poker_results_categoria ON poker_results(categoria);
CREATE INDEX IF NOT EXISTS idx_poker_results_sala ON poker_results(sala);

-- Crear usuario administrador por defecto
INSERT INTO users (id, username, email, password_hash, is_admin, is_active) 
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid, 
    'admin', 
    'admin@poker-results.com', 
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4j8J8J8J8J', -- admin123
    TRUE, 
    TRUE
) ON CONFLICT (username) DO NOTHING;

-- Habilitar Row Level Security (RLS)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE poker_results ENABLE ROW LEVEL SECURITY;

-- Políticas de seguridad para usuarios
CREATE POLICY "Users can view their own data" ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Admins can view all users" ON users
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM users 
            WHERE id = auth.uid() 
            AND is_admin = TRUE
        )
    );

-- Políticas de seguridad para resultados de poker
CREATE POLICY "Users can view their own poker results" ON poker_results
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY "Users can insert their own poker results" ON poker_results
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update their own poker results" ON poker_results
    FOR UPDATE USING (user_id = auth.uid());

CREATE POLICY "Users can delete their own poker results" ON poker_results
    FOR DELETE USING (user_id = auth.uid());

CREATE POLICY "Admins can view all poker results" ON poker_results
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM users 
            WHERE id = auth.uid() 
            AND is_admin = TRUE
        )
    );

-- Crear función para obtener estadísticas de usuario
CREATE OR REPLACE FUNCTION get_user_stats(user_id_param UUID)
RETURNS TABLE (
    total_registros BIGINT,
    total_importe DECIMAL,
    torneos_jugados BIGINT,
    salas_activas BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_registros,
        COALESCE(SUM(importe), 0) as total_importe,
        COUNT(CASE WHEN categoria = 'Torneo' AND tipo_movimiento = 'Buy In' THEN 1 END) as torneos_jugados,
        COUNT(DISTINCT sala) as salas_activas
    FROM poker_results 
    WHERE poker_results.user_id = user_id_param;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Crear función para obtener análisis por tipo de juego
CREATE OR REPLACE FUNCTION get_game_analysis(user_id_param UUID)
RETURNS TABLE (
    tipo_juego VARCHAR,
    total_torneos BIGINT,
    total_ganancias DECIMAL,
    total_invertido DECIMAL,
    roi DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pr.tipo_juego,
        COUNT(CASE WHEN pr.tipo_movimiento = 'Buy In' THEN 1 END) as total_torneos,
        COALESCE(SUM(CASE WHEN pr.importe > 0 THEN pr.importe ELSE 0 END), 0) as total_ganancias,
        COALESCE(SUM(CASE WHEN pr.importe < 0 THEN ABS(pr.importe) ELSE 0 END), 0) as total_invertido,
        CASE 
            WHEN SUM(CASE WHEN pr.importe < 0 THEN ABS(pr.importe) ELSE 0 END) > 0 
            THEN ((SUM(CASE WHEN pr.importe > 0 THEN pr.importe ELSE 0 END) - SUM(CASE WHEN pr.importe < 0 THEN ABS(pr.importe) ELSE 0 END)) / SUM(CASE WHEN pr.importe < 0 THEN ABS(pr.importe) ELSE 0 END)) * 100
            ELSE 0 
        END as roi
    FROM poker_results pr
    WHERE pr.user_id = user_id_param 
    AND pr.categoria = 'Torneo'
    GROUP BY pr.tipo_juego
    ORDER BY total_torneos DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
