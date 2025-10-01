-- Script para corregir las políticas RLS en Supabase
-- Ejecutar este script en el SQL Editor de Supabase

-- Eliminar políticas existentes de la tabla users
DROP POLICY IF EXISTS "Users can view own data" ON users;
DROP POLICY IF EXISTS "Users can insert own data" ON users;
DROP POLICY IF EXISTS "Users can update own data" ON users;
DROP POLICY IF EXISTS "Users can delete own data" ON users;

-- Crear políticas RLS para la tabla users
-- Permitir que cualquier usuario autenticado pueda insertar (para registro)
CREATE POLICY "Allow authenticated users to insert" ON users 
    FOR INSERT 
    TO authenticated 
    WITH CHECK (true);

-- Permitir que los usuarios vean sus propios datos
CREATE POLICY "Users can view own data" ON users 
    FOR SELECT 
    USING (auth.uid()::text = id::text);

-- Permitir que los usuarios actualicen sus propios datos
CREATE POLICY "Users can update own data" ON users 
    FOR UPDATE 
    USING (auth.uid()::text = id::text);

-- Permitir que los usuarios eliminen sus propios datos
CREATE POLICY "Users can delete own data" ON users 
    FOR DELETE 
    USING (auth.uid()::text = id::text);

-- Verificar las políticas creadas
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies 
WHERE tablename = 'users';
