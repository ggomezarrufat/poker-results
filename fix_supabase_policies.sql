-- Script para arreglar las políticas de Supabase
-- Ejecutar este script en el SQL Editor de Supabase

-- 1. Eliminar TODAS las políticas existentes
DROP POLICY IF EXISTS "Users can view their own data" ON users;
DROP POLICY IF EXISTS "Admins can view all users" ON users;
DROP POLICY IF EXISTS "Users can view their own poker results" ON poker_results;
DROP POLICY IF EXISTS "Users can insert their own poker results" ON poker_results;
DROP POLICY IF EXISTS "Users can update their own poker results" ON poker_results;
DROP POLICY IF EXISTS "Users can delete their own poker results" ON poker_results;
DROP POLICY IF EXISTS "Admins can view all poker results" ON poker_results;
DROP POLICY IF EXISTS "Allow all users to view users table" ON users;
DROP POLICY IF EXISTS "Allow all users to insert users" ON users;
DROP POLICY IF EXISTS "Allow all users to update users" ON users;
DROP POLICY IF EXISTS "Allow all users to view poker results" ON poker_results;
DROP POLICY IF EXISTS "Allow all users to insert poker results" ON poker_results;
DROP POLICY IF EXISTS "Allow all users to update poker results" ON poker_results;
DROP POLICY IF EXISTS "Allow all users to delete poker results" ON poker_results;

-- 2. Deshabilitar RLS completamente
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE poker_results DISABLE ROW LEVEL SECURITY;

-- 3. Verificar que las tablas existen
SELECT 'users table exists' as status WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users');
SELECT 'poker_results table exists' as status WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'poker_results');

-- 4. Mostrar usuarios existentes
SELECT username, email, is_admin, is_active FROM users LIMIT 5;
