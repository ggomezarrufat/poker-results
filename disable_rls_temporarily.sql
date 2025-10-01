-- Script para deshabilitar RLS temporalmente y permitir registro
-- Ejecutar este script en el SQL Editor de Supabase

-- Deshabilitar RLS temporalmente para permitir registro
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE poker_results DISABLE ROW LEVEL SECURITY;

-- Verificar que RLS está deshabilitado
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE tablename IN ('users', 'poker_results');
