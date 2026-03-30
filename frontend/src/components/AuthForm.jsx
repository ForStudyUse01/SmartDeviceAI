import { useState } from 'react'

const initialState = { email: '', password: '' }

export function AuthForm({ mode, onSubmit, loading, error }) {
  const [form, setForm] = useState(initialState)

  function handleChange(event) {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  function handleSubmit(event) {
    event.preventDefault()
    onSubmit(form)
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor={`${mode}-email`}>Email</label>
        <input
          id={`${mode}-email`}
          name="email"
          type="email"
          autoComplete="email"
          required
          value={form.email}
          onChange={handleChange}
          placeholder="operator@smartdeviceai.com"
        />
      </div>
      <div className="field">
        <label htmlFor={`${mode}-password`}>Password</label>
        <input
          id={`${mode}-password`}
          name="password"
          type="password"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          minLength={6}
          required
          value={form.password}
          onChange={handleChange}
          placeholder="Minimum 6 characters"
        />
      </div>
      {error ? <div className="error-banner">{error}</div> : null}
      <button className="primary-button" type="submit" disabled={loading}>
        {loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Create account'}
      </button>
    </form>
  )
}
