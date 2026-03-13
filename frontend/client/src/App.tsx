import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/not-found";
import AuthPage from "@/pages/auth";
import Dashboard from "@/pages/dashboard";
import Students from "@/pages/students";
import Guardians from "@/pages/guardians";
import Attendance from "@/pages/attendance";
import Gates from "@/pages/gates";
import Tracking from "@/pages/tracking";
import Alerts from "@/pages/alerts";
import Security from "@/pages/security";
import Reports from "@/pages/reports";
import TrainingData from "@/pages/training-data";
import Staff from "@/pages/staff";
import Settings from "@/pages/settings";

function Router() {
  return (
    <Switch>
      <Route path="/" component={AuthPage} />
      <Route path="/auth" component={AuthPage} />
      <Route path="/dashboard" component={Dashboard} />
      <Route path="/students" component={Students} />
      <Route path="/guardians" component={Guardians} />
      <Route path="/attendance" component={Attendance} />
      <Route path="/gates" component={Gates} />
      <Route path="/tracking" component={Tracking} />
      <Route path="/alerts" component={Alerts} />
      <Route path="/security" component={Security} />
      <Route path="/reports" component={Reports} />
      <Route path="/training-data" component={TrainingData} />
      <Route path="/staff" component={Staff} />
      <Route path="/settings" component={Settings} />

      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Router />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
