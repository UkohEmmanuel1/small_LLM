'use client';
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
type Key = { id: number; name: string; prefix: string; revoked: boolean; created_at: string };
const getToken = () => typeof window === 'undefined' ? '' : localStorage.getItem('smallllm_token') || '';

export default function Developers() {
  const [keys, setKeys] = useState<Key[]>([]);
  const [name, setName] = useState('My agent');
  const [fresh, setFresh] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API}/api/keys/`, { headers: { Authorization: `Token ${getToken()}` } });
      if (!response.ok) throw new Error(response.status === 401 || response.status === 403 ? 'Sign in first to manage API keys.' : 'Could not load API keys.');
      setKeys(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function create() {
    setError('');
    setFresh('');
    try {
      const response = await fetch(`${API}/api/keys/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Token ${getToken()}` },
        body: JSON.stringify({ name }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not create key.');
      setFresh(data.key);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed.');
    }
  }

  async function revoke(id: number) {
    const response = await fetch(`${API}/api/keys/${id}/`, {
      method: 'DELETE',
      headers: { Authorization: `Token ${getToken()}` },
    });
    if (response.ok) await load();
    else setError('Could not revoke this key.');
  }

  return <main style={{ maxWidth: 850, margin: '8vh auto', padding: 24 }}>
    <div className="brand">small<span>_</span>LLM</div>
    <h1>Developer console</h1>
    <p style={{ color: '#969cac' }}>Create credentials for Vonk, agents and your applications. Store keys as secrets; never ship them in browser code.</p>
    <section className="composer">
      <h3>Create API key</h3>
      <input value={name} onChange={event => setName(event.target.value)} placeholder="Key name" style={{ width: '100%', padding: 12, background: '#090b10', color: 'white', border: '1px solid #343b49', borderRadius: 8 }}/>
      <button className="send" style={{ marginTop: 12 }} onClick={create}>Generate key</button>
      {fresh && <div style={{ marginTop: 16, padding: 14, border: '1px solid #566d3a', borderRadius: 10, overflowWrap: 'anywhere' }}>
        <strong>Copy this key now. It will not be shown again.</strong>
        <p>{fresh}</p>
        <button className="send" onClick={() => navigator.clipboard.writeText(fresh)}>Copy key</button>
      </div>}
    </section>
    {error && <p role="alert" style={{ color: '#ff9c9c' }}>{error}</p>}
    <h2 style={{ marginTop: 30 }}>Your API keys</h2>
    {loading ? 'Loading…' : keys.length === 0 ? 'No API keys yet.' : keys.map(key => <div key={key.id} className="message" style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
      <div><strong>{key.name}</strong><div style={{ color: '#969cac' }}>{key.prefix}… · {key.revoked ? 'Revoked' : 'Active'}</div></div>
      {!key.revoked && <button className="send" onClick={() => revoke(key.id)}>Revoke</button>}
    </div>)}
    <p style={{ marginTop: 24, color: '#969cac' }}>API base URL: <code>{API}/v1</code></p>
    <pre className="message" style={{ overflowX: 'auto' }}>{`from openai import OpenAI
client = OpenAI(base_url="${API}/v1", api_key="YOUR_SMALL_LLM_KEY")`}</pre>
    <Link href="/">← Back to chat</Link>
  </main>;
}
