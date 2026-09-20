import { Navigate, Route, Routes } from 'react-router-dom';

import CustomScrollbar from './components/CustomScrollbar';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import RiskAnalysis from './pages/RiskAnalysis';
import Threats from './pages/Threats';
import Scenarios from './pages/Scenarios';
import Compliance from './pages/Compliance';
import Investment from './pages/Investment';
import Remediation from './pages/Remediation';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import Network from './pages/Network';
import Insights from './pages/Insights';
import Audit from './pages/Audit';
import { auth } from './lib/api';

function RequireAuth({ children }) {
  return auth.token() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <>
      <CustomScrollbar />
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route
          path="/app"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="network" element={<Network />} />
          <Route path="risk" element={<RiskAnalysis />} />
          <Route path="threats" element={<Threats />} />
          <Route path="scenarios" element={<Scenarios />} />
          <Route path="compliance" element={<Compliance />} />
          <Route path="investment" element={<Investment />} />
          <Route path="remediation" element={<Remediation />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
          <Route path="insights" element={<Insights />} />
          <Route path="audit" element={<Audit />} />
        </Route>

        <Route path="/" element={<Navigate to="/app" replace />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </>
  );
}
