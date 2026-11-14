'use client';
import { FormEvent, useState } from 'react';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      const response = await fetch(`${API}/api/auth/token/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();
      if (!response.ok || !data.token) throw new Error(data.non_field_errors?.[0] || 'Incorrect username or password.');
      localStorage.setItem('smallllm_token', data.token);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed.');
    }
  }

  return <main style={{ maxWidth: 460, margin: '12vh auto', padding: 28 }}>
    <div className="brand">small<span>_</span>LLM</div>
    <h1>Welcome back</h1>
    <p style={{ color: '#969cac' }}>Sign in to access your saved conversations and developer keys.</p>
    {done ? <p>You are signed in. <Link href="/">Return to chat →</Link></p> : <form onSubmit={submit} className="composer">
      <input required autoComplete="username" placeholder="Username" value={username} onChange={event => setUsername(event.target.value)} style={field}/>
      <input required type="password" autoComplete="current-password" placeholder="Password" value={password} onChange={event => setPassword(event.target.value)} style={field}/>
      {error && <p role="alert" style={{ color: '#ff9c9c' }}>{error}</p>}
      <button className="send">Sign in</button>
    </form>}
    <p style={{ color: '#969cac', marginTop: 20 }}>New here? <Link href="/signup">Create an account</Link></p>
    <p><Link href="/">← Back to chat</Link></p>
  </main>;
}

const field = { display: 'block', width: '100%', padding: 13, marginBottom: 12, borderRadius: 9, border: '1px solid #343b49', background: '#0b0d12', color: 'white' };
