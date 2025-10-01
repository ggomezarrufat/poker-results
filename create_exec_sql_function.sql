-- Función para ejecutar SQL dinámico en Supabase
-- Esta función permite ejecutar queries SQL desde la aplicación

CREATE OR REPLACE FUNCTION exec_sql(sql TEXT)
RETURNS TABLE(result JSONB)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Ejecutar el SQL y retornar el resultado
    RETURN QUERY EXECUTE 'SELECT to_jsonb(' || sql || ') as result';
EXCEPTION
    WHEN OTHERS THEN
        -- En caso de error, retornar el mensaje de error
        RETURN QUERY SELECT jsonb_build_object('error', SQLERRM) as result;
END;
$$;

-- Dar permisos para ejecutar la función
GRANT EXECUTE ON FUNCTION exec_sql(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION exec_sql(TEXT) TO anon;
