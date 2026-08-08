'use client';

import React, { useState } from 'react';
import { Mic, ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/shadcn/utils';

function WelcomeImage() {
  return (
    <div className="relative mb-6 flex items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6">
      <Mic className="text-primary size-12 animate-pulse" />
      <span className="absolute -top-1 -right-1 flex h-3 w-3">
        <span className="bg-primary absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"></span>
        <span className="bg-primary relative inline-flex h-3 w-3 rounded-full"></span>
      </span>
    </div>
  );
}

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
  ...props
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  const [permissionState, setPermissionState] = useState<'prompt' | 'checking' | 'denied'>(
    'prompt'
  );

  const handleStartClick = async () => {
    setPermissionState('checking');
    try {
      // Request mic permissions
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Clean up tracks immediately
      stream.getTracks().forEach((track) => track.stop());
      setPermissionState('prompt');
      onStartCall();
    } catch (err: unknown) {
      console.error('Microphone access denied:', err);
      setPermissionState('denied');
    }
  };

  return (
    <div
      ref={ref}
      className="flex min-h-[70vh] flex-col items-center justify-center px-4"
      {...props}
    >
      <section className="flex w-full max-w-md flex-col items-center justify-center text-center">
        {permissionState !== 'denied' ? (
          <>
            <WelcomeImage />

            {/* State status label */}
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-950/30 px-3 py-1 text-emerald-500">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
              <span className="font-mono text-xs font-black tracking-wider uppercase">
                Ready / तैयार
              </span>
            </div>

            <h1 className="text-foreground font-sans text-3xl font-black tracking-tight uppercase md:text-4xl">
              RAKSHA / रक्षा
            </h1>

            <p className="text-muted-foreground mt-2 text-sm leading-relaxed font-medium">
              Disaster-response voice assistant. Speak live for calm, practical safety guidance in
              emergency situations.
            </p>
            <p className="text-muted-foreground/60 mt-1 text-xs font-semibold">
              आपातकालीन स्थितियों में तत्काल सहायता और सुरक्षा मार्गदर्शन के लिए लाइव बात करें।
            </p>

            <Button
              size="lg"
              disabled={permissionState === 'checking'}
              onClick={handleStartClick}
              className={cn(
                'mt-8 w-64 rounded-xl py-6 font-mono text-sm font-black tracking-wider uppercase',
                'bg-primary text-primary-foreground hover:bg-primary/90 transition-colors'
              )}
            >
              {permissionState === 'checking' ? 'Checking Mic...' : startButtonText}
            </Button>
          </>
        ) : (
          <div className="border-destructive bg-destructive/5 relative w-full overflow-hidden rounded-2xl border p-6 text-left">
            {/* Command-center status indicator */}
            <div className="bg-destructive/5 absolute top-0 right-0 flex h-24 w-24 translate-x-8 -translate-y-8 items-center justify-center rounded-full">
              <ShieldAlert className="text-destructive/20 size-10" />
            </div>

            <div className="flex items-start gap-3">
              <div className="bg-destructive/10 text-destructive mt-0.5 rounded-lg p-2">
                <ShieldAlert className="size-6" />
              </div>
              <div>
                <h3 className="text-destructive font-mono text-sm font-black tracking-wider uppercase">
                  Microphone Access Blocked
                </h3>
                <h4 className="text-destructive/80 -mt-0.5 font-mono text-xs font-black tracking-wider uppercase">
                  माइक्रोफ़ोन ब्लॉक है
                </h4>
              </div>
            </div>

            {/* Instruction body */}
            <div className="border-destructive/10 mt-4 space-y-3 border-t pt-4 text-zinc-300">
              <div>
                <span className="text-destructive mb-1 block font-mono text-xs font-bold tracking-wider uppercase">
                  Instructions:
                </span>
                <p className="font-sans text-xs leading-relaxed">
                  Raksha requires microphone access to hear your voice. Please click the microphone
                  lock or site settings icon in your browser&apos;s address bar, change the
                  permission to <strong>Allow</strong>, and retry.
                </p>
              </div>

              <div className="border-t border-zinc-800/50 pt-2">
                <span className="text-destructive/80 mb-1 block font-mono text-xs font-bold tracking-wider uppercase">
                  निर्देश:
                </span>
                <p className="font-sans text-xs leading-relaxed text-zinc-400">
                  रक्षा को आपकी आवाज़ सुनने के लिए माइक्रोफ़ोन एक्सेस की आवश्यकता है। कृपया अपने
                  ब्राउज़र के एड्रेस बार में माइक्रोफ़ोन/साइट सेटिंग्स आइकन पर क्लिक करें, अनुमति को{' '}
                  <strong>Allow (अनुमति दें)</strong> पर बदलें, और पुनः प्रयास करें।
                </p>
              </div>
            </div>

            {/* Retry CTA */}
            <Button
              onClick={handleStartClick}
              variant="destructive"
              className="mt-6 w-full rounded-xl py-5 font-mono text-xs font-black tracking-wider uppercase"
            >
              Retry / पुनः प्रयास करें
            </Button>
          </div>
        )}
      </section>

      {/* Info footer */}
      <div className="mt-12 max-w-sm text-center">
        <p className="text-muted-foreground/40 font-mono text-[10px] leading-relaxed tracking-widest uppercase">
          Emergency Command Center Platform · works in English, Hindi & Hinglish
        </p>
      </div>
    </div>
  );
};
