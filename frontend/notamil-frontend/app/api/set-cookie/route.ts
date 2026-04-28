import { NextResponse } from 'next/server'
// Se quiser verificar o token, importe seu firebaseAdmin e chame verifyIdToken
// import { adminAuth } from '@/services/firebaseAdmin' // Exemplo

export async function POST(request: Request) {
  try {
    const { token } = await request.json()
    if (!token) {
      return NextResponse.json({ error: 'No token provided' }, { status: 400 })
    }

    // (Opcional) Se quiser verificar no servidor:
    // const decoded = await adminAuth.verifyIdToken(token)
    // console.log('Token decodificado:', decoded)

    // Se chegou até aqui, token é válido (ou assumimos que é).
    // Vamos setar um cookie "accessToken" com esse valor.
    // Exemplo de cookie sem httpOnly (para simplificar):
    // se quiser httpOnly, Secure, etc., veja mais abaixo

    const response = NextResponse.json({ message: 'Cookie set' })
    response.cookies.set({
      name: 'accessToken',
      value: token,
      path: '/',       // cookie em todo o site
      httpOnly: true,  // cookie não acessível via JS (mais seguro)
      secure: true,    // só funciona em HTTPS
      sameSite: 'strict',
      maxAge: 60 * 60  // 1 hora, por exemplo
    })
    return response

  } catch (err) {
    console.error(err)
    return NextResponse.json({ error: 'Something went wrong' }, { status: 500 })
  }
}
