'use client';

import React, { useMemo, useState } from 'react';
import { TokenSource } from 'livekit-client';
import { useSession } from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react/dist/ssr';
import type { AppConfig } from '@/app-config';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/ui/sonner';
import { useAgentErrors } from '@/hooks/useAgentErrors';
import { useDebugMode } from '@/hooks/useDebug';
import { cn } from '@/lib/shadcn/utils';
import { getSandboxTokenSource } from '@/lib/utils';

const IN_DEVELOPMENT = process.env.NODE_ENV !== 'production';

function AppSetup() {
  useDebugMode({ enabled: IN_DEVELOPMENT });
  useAgentErrors();

  return null;
}

interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
  const tokenSource = useMemo(() => {
    return typeof process.env.NEXT_PUBLIC_CONN_DETAILS_ENDPOINT === 'string'
      ? getSandboxTokenSource(appConfig)
      : TokenSource.endpoint('/api/token');
  }, [appConfig]);

  const session = useSession(
    tokenSource,
    appConfig.agentName ? { agentName: appConfig.agentName } : undefined
  );

  const [lowBandwidthMode, setLowBandwidthMode] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('raksha_low_bandwidth') === 'true';
    }
    return false;
  });

  const toggleLowBandwidth = () => {
    setLowBandwidthMode((prev) => {
      const next = !prev;
      if (typeof window !== 'undefined') {
        localStorage.setItem('raksha_low_bandwidth', String(next));
      }
      return next;
    });
  };

  return (
    <AgentSessionProvider session={session}>
      <AppSetup />

      {/* Global Responsive Header */}
      <header className="fixed top-0 left-0 z-50 flex w-full flex-row items-center justify-between p-4 md:p-6">
        <a
          target="_blank"
          rel="noopener noreferrer"
          href="https://livekit.io"
          className="hidden scale-100 transition-transform duration-300 hover:scale-110 sm:block"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={appConfig.logo}
            alt={`${appConfig.companyName} Logo`}
            className="block size-6 dark:hidden"
          />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={appConfig.logoDark ?? appConfig.logo}
            alt={`${appConfig.companyName} Logo`}
            className="hidden size-6 dark:block"
          />
        </a>

        <div className="ml-auto flex flex-col items-end gap-2 sm:flex-row sm:items-center sm:gap-3">
          <span className="text-foreground font-mono text-[10px] font-bold tracking-wider uppercase md:text-xs">
            Built with{' '}
            <a
              target="_blank"
              rel="noopener noreferrer"
              href="https://docs.livekit.io/agents"
              className="underline underline-offset-4"
            >
              LiveKit Agents
            </a>
          </span>
          {session.isConnected && (
            <button
              onClick={toggleLowBandwidth}
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 font-mono text-[10px] font-bold tracking-wider uppercase shadow-lg transition-all duration-200 md:text-xs',
                lowBandwidthMode
                  ? 'bg-primary/10 border-primary text-primary'
                  : 'border-zinc-800 bg-zinc-950/80 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
              )}
            >
              <span
                className={cn(
                  'h-1.5 w-1.5 shrink-0 rounded-full',
                  lowBandwidthMode ? 'bg-primary animate-pulse' : 'bg-zinc-500'
                )}
              />
              <span>Low Bandwidth / कम डेटा: {lowBandwidthMode ? 'ON' : 'OFF'}</span>
            </button>
          )}
        </div>
      </header>

      <main className="grid h-svh grid-cols-1 place-content-center">
        <ViewController appConfig={appConfig} lowBandwidthMode={lowBandwidthMode} />
      </main>
      <StartAudioButton label="Start Audio" />
      <Toaster
        icons={{
          warning: <WarningIcon weight="bold" />,
        }}
        position="top-center"
        className="toaster group"
        style={
          {
            '--normal-bg': 'var(--popover)',
            '--normal-text': 'var(--popover-foreground)',
            '--normal-border': 'var(--border)',
          } as React.CSSProperties
        }
      />
    </AgentSessionProvider>
  );
}
