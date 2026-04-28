'use client'

import { ReactNode, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

interface RouteGuardProps {
  children: ReactNode
  requiredRole?: string
  fallback?: ReactNode
}

export default function RouteGuard({ 
  children, 
  requiredRole,
  fallback = <div className="flex h-screen w-full items-center justify-center">Carregando...</div>
}: RouteGuardProps) {
  const [authorized, setAuthorized] = useState(false)
  const router = useRouter()

  useEffect(() => {
    // Função para verificar autorização
    const checkAuth = () => {
      // Verificar localStorage diretamente
      const userId = localStorage.getItem('user_id')
      const userRole = localStorage.getItem('user_role')
      
      console.log("RouteGuard verificando acesso:", { 
        userId, 
        userRole, 
        requiredRole,
        authorized
      })

      // Se não está autenticado
      if (!userId) {
        console.log("Usuário não autenticado, redirecionando para login")
        router.replace('/login')
        return false
      }

      // Se o role é requerido mas o usuário não tem o role correto
      if (requiredRole && userRole !== requiredRole) {
        console.log(`Acesso negado: usuário tem role "${userRole}", mas "${requiredRole}" é necessário`)
        // Use location.href para um redirecionamento forçado
        window.location.href = '/dashboard'
        return false
      }

      // Se passou por todas as verificações
      return true
    }

    // Verificar autorização e atualizar estado
    const authCheck = checkAuth()
    setAuthorized(authCheck)
  }, [router, requiredRole])

  // Enquanto verifica, mostra o fallback
  if (!authorized) {
    return fallback
  }

  // Se está autorizado, mostra o conteúdo
  return <>{children}</>
}