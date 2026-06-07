import { createBrowserRouter } from 'react-router-dom'
import { LoginPage } from '@/pages/login'
import { RegisterPage } from '@/pages/register'
import { DashboardPage } from '@/pages/dashboard'
import { WatchlistPage } from '@/pages/watchlist'
import { PortfolioPage } from '@/pages/portfolio'
import { MarketsPage } from '@/pages/markets'
import { AnalyticsPage } from '@/pages/analytics'
import { AIChatPage } from '@/pages/ai-chat'
import { ScannerPage } from '@/pages/scanner'
import { SignalsPage } from '@/pages/signals'
import { AILabPage } from '@/pages/ai-lab'
import { StrategiesPage } from '@/pages/strategies'
import { BacktestingPage } from '@/pages/backtesting'
import { AlertsPage } from '@/pages/alerts'
import { JournalPage } from '@/pages/journal'
import { ProfilePage } from '@/pages/profile'
import { SupportPage } from '@/pages/support'
import { AdminUsersPage } from '@/pages/admin-users'
import { AdminMLTrainingPage } from '@/pages/admin-ml-training'
import { AdminSystemStatusPage } from '@/pages/admin-system-status'
import { TickerPage } from '@/pages/ticker'
import { SettingsPage } from '@/pages/settings'
import { NotFoundPage } from '@/pages/not-found'
import { AppLayout } from '@/app/layouts/app-layout'
import { AuthLayout } from '@/app/layouts/auth-layout'
import { ProtectedRoute } from '@/features/auth/components/protected-route'

export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'markets', element: <MarketsPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: 'ai-chat', element: <AIChatPage /> },
      { path: 'scanner', element: <ScannerPage /> },
      { path: 'signals', element: <SignalsPage /> },
      { path: 'ai-lab', element: <AILabPage /> },
      { path: 'strategies', element: <StrategiesPage /> },
      { path: 'backtesting', element: <BacktestingPage /> },
      { path: 'alerts', element: <AlertsPage /> },
      { path: 'journal', element: <JournalPage /> },
      { path: 'profile', element: <ProfilePage /> },
      { path: 'support', element: <SupportPage /> },
      { path: 'admin/users', element: <AdminUsersPage /> },
      { path: 'admin/ml-training', element: <AdminMLTrainingPage /> },
      { path: 'admin/system-status', element: <AdminSystemStatusPage /> },
      { path: 'watchlist', element: <WatchlistPage /> },
      { path: 'portfolio', element: <PortfolioPage /> },
      { path: 'ticker/:id', element: <TickerPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
  {
    path: '/',
    element: <AuthLayout />,
    children: [
      {
        path: 'login',
        element: <LoginPage />,
      },
      {
        path: 'register',
        element: <RegisterPage />,
      },
    ],
  },

  { path: '*', element: <NotFoundPage /> },
])
