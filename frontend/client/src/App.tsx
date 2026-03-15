import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/not-found";
import Dashboard from "@/pages/dashboard";
import Guardians from "@/pages/guardians";
import Gates from "@/pages/gates";
import Tracking from "@/pages/tracking";
import Security from "@/pages/security";
import Staff from "@/pages/staff";
import Settings from "@/pages/settings";

function Router() {
  return (
    <Switch>
      <Route path="/dashboard" component={Dashboard} />
      <Route path="/guardians" component={Guardians} />
      <Route path="/gates" component={Gates} />
      <Route path="/tracking" component={Tracking} />
      <Route path="/security" component={Security} />
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
