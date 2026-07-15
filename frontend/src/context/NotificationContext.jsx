import { createContext, useContext, useState, useCallback } from 'react'

const NotificationContext = createContext(null)

let _id = 0

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([])

  const addNotification = useCallback((type, message, duration = 5000) => {
    const id = ++_id
    setNotifications((prev) => [...prev, { id, type, message, removing: false }])
    setTimeout(() => {
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, removing: true } : n)),
      )
      setTimeout(() => {
        setNotifications((prev) => prev.filter((n) => n.id !== id))
      }, 300)
    }, duration)
  }, [])

  const notify = {
    success: (msg) => addNotification('success', msg),
    error: (msg) => addNotification('error', msg),
    info: (msg) => addNotification('info', msg),
    warning: (msg) => addNotification('warning', msg),
  }

  return (
    <NotificationContext.Provider value={notify}>
      {children}
      <NotificationContainer notifications={notifications} />
    </NotificationContext.Provider>
  )
}

function NotificationContainer({ notifications }) {
  const colors = {
    success: 'bg-emerald-500',
    error: 'bg-red-500',
    info: 'bg-blue-500',
    warning: 'bg-orange-500',
  }
  const icons = {
    success: '✓',
    error: '✕',
    info: 'ℹ',
    warning: '⚠',
  }

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-3 pointer-events-none">
      {notifications.map((n) => (
        <div
          key={n.id}
          className={`pointer-events-auto flex items-center gap-3 px-5 py-3 rounded-xl shadow-2xl text-white text-sm font-medium ${colors[n.type]} ${n.removing ? 'animate-toast-out' : 'animate-toast-in'}`}
        >
          <span className="text-lg leading-none">{icons[n.type]}</span>
          <span>{n.message}</span>
        </div>
      ))}
    </div>
  )
}

export function useNotification() {
  const ctx = useContext(NotificationContext)
  if (!ctx) throw new Error('useNotification must be used within NotificationProvider')
  return ctx
}

export default NotificationContext
