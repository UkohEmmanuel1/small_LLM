'use client';
import Link from 'next/link';
export default function Account(){return <main style={{maxWidth:600,margin:'10vh auto',padding:24}}><div className="brand">small<span>_</span>LLM</div><h1>Your account</h1><p style={{color:'#969cac'}}>Manage your small_LLM workspace and developer credentials.</p><p><Link href="/signup">Create account</Link></p><p><Link href="/developers">Developer console →</Link></p><p><Link href="/">← Back to chat</Link></p></main>}
