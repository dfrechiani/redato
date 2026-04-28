'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

export function useAuth(requiredRole?: string) {
  const [user, setUser] = useState<{
    id: string | null;
    role: string | null;
    name: string | null;
    isLoading: boolean;
    isAuthenticated: boolean;
  }>({
    id: null,
    role: null,
    name: null,
    isLoading: true,
    isAuthenticated: false,
  })

  const router = useRouter()

  useEffect(() => {
    // Verificar autenticação quando o componente montar
    const checkAuth = () => {
      try {
        const userId = localStorage.getItem('user_id')
        const userRole = localStorage.getItem('user_role')
        const userName = localStorage.getItem('user_name')

        const isAuthenticated = !!userId

        // Se não está autenticado, redireciona para login
        if (!isAuthenticated) {
          router.push('/login')
          return
        }

        // Se um role específico é exigido e o usuário não tem esse role
        if (requiredRole && userRole !== requiredRole) {
          console.log(`Acesso negado: Usuário tem role ${userRole}, mas ${requiredRole} é necessário`)
          router.push('/dashboard') // Redireciona para dashboard ou página de acesso negado
          return
        }

        setUser({
          id: userId,
          role: userRole,
          name: userName,
          isLoading: false,
          isAuthenticated: true,
        })
      } catch (error) {
        console.error('Erro ao verificar autenticação:', error)
        // Em caso de erro, assume que não está autenticado
        setUser({
          id: null,
          role: null,
          name: null,
          isLoading: false,
          isAuthenticated: false,
        })
        router.push('/login')
      }
    }

    checkAuth()
  }, [router, requiredRole])

  return user
}