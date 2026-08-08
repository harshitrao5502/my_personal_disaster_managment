import React, { useMemo } from 'react';
import { Track } from 'livekit-client';
import { AnimatePresence, type MotionProps, motion } from 'motion/react';
import {
  type TrackReference,
  VideoTrack,
  useLocalParticipant,
  useTracks,
  useVoiceAssistant,
} from '@livekit/components-react';
import { cn } from '@/lib/shadcn/utils';
import { AudioVisualizer } from './audio-visualizer';

const ANIMATION_TRANSITION: MotionProps['transition'] = {
  type: 'spring',
  stiffness: 675,
  damping: 75,
  mass: 1,
};

const tileViewClassNames = {
  // GRID
  // 2 Columns x 3 Rows
  grid: [
    'h-full w-full',
    'grid gap-x-2 place-content-center',
    'grid-cols-[1fr_1fr] grid-rows-[90px_1fr_90px]',
  ],
  // Agent
  // chatOpen: true,
  // hasSecondTile: true
  // layout: Column 1 / Row 1
  // align: x-end y-center
  agentChatOpenWithSecondTile: ['col-start-1 row-start-1', 'self-center justify-self-end'],
  // Agent
  // chatOpen: true,
  // hasSecondTile: false
  // layout: Column 1 / Row 1 / Column-Span 2
  // align: x-center y-center
  agentChatOpenWithoutSecondTile: ['col-start-1 row-start-1', 'col-span-2', 'place-content-center'],
  // Agent
  // chatOpen: false
  // layout: Column 1 / Row 1 / Column-Span 2 / Row-Span 3
  // align: x-center y-center
  agentChatClosed: ['col-start-1 row-start-1', 'col-span-2 row-span-3', 'place-content-center'],
  // Second tile
  // chatOpen: true,
  // hasSecondTile: true
  // layout: Column 2 / Row 1
  // align: x-start y-center
  secondTileChatOpen: ['col-start-2 row-start-1', 'self-center justify-self-start'],
  // Second tile
  // chatOpen: false,
  // hasSecondTile: false
  // layout: Column 2 / Row 2
  // align: x-end y-end
  secondTileChatClosed: ['col-start-2 row-start-3', 'place-content-end'],
};

export function useLocalTrackRef(source: Track.Source) {
  const { localParticipant } = useLocalParticipant();
  const publication = localParticipant.getTrackPublication(source);
  const trackRef = useMemo<TrackReference | undefined>(
    () => (publication ? { source, participant: localParticipant, publication } : undefined),
    [source, publication, localParticipant]
  );
  return trackRef;
}

const getStateLabel = (state: string) => {
  switch (state) {
    case 'connecting':
    case 'initializing':
      return {
        en: 'CONNECTING',
        hi: 'जोड़ रहा है...',
        colorClass: 'text-zinc-400',
        dotColor: 'bg-zinc-400',
      };
    case 'listening':
      return {
        en: 'LISTENING',
        hi: 'सुन रहा हूँ',
        colorClass: 'text-primary',
        dotColor: 'bg-primary animate-pulse',
      };
    case 'thinking':
      return {
        en: 'THINKING',
        hi: 'सोच रहा हूँ',
        colorClass: 'text-primary',
        dotColor: 'bg-primary animate-pulse',
      };
    case 'speaking':
      return {
        en: 'SPEAKING',
        hi: 'बोल रहा हूँ',
        colorClass: 'text-primary',
        dotColor: 'bg-primary animate-pulse',
      };
    case 'disconnected':
      return {
        en: 'CALL ENDED',
        hi: 'कॉल समाप्त',
        colorClass: 'text-red-500',
        dotColor: 'bg-red-500',
      };
    default:
      return {
        en: 'CONNECTING',
        hi: 'जोड़ रहा है...',
        colorClass: 'text-zinc-400',
        dotColor: 'bg-zinc-400',
      };
  }
};

interface TileLayoutProps {
  chatOpen: boolean;
  lowBandwidthMode?: boolean;
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerWaveLineWidth?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerBarCount?: number;
}

export function TileLayout({
  chatOpen,
  lowBandwidthMode = false,
  audioVisualizerType,
  audioVisualizerColor,
  audioVisualizerColorShift,
  audioVisualizerBarCount,
  audioVisualizerRadialBarCount,
  audioVisualizerRadialRadius,
  audioVisualizerGridRowCount,
  audioVisualizerGridColumnCount,
  audioVisualizerWaveLineWidth,
}: TileLayoutProps) {
  const { state: agentState, videoTrack: agentVideoTrack } = useVoiceAssistant();
  const [screenShareTrack] = useTracks([Track.Source.ScreenShare]);
  const cameraTrack: TrackReference | undefined = useLocalTrackRef(Track.Source.Camera);

  const isCameraEnabled = cameraTrack && !cameraTrack.publication.isMuted;
  const isScreenShareEnabled = screenShareTrack && !screenShareTrack.publication.isMuted;

  const animationDelay = chatOpen ? 0 : 0.15;
  const isAvatar = agentVideoTrack !== undefined;
  const videoWidth = agentVideoTrack?.publication.dimensions?.width ?? 0;
  const videoHeight = agentVideoTrack?.publication.dimensions?.height ?? 0;

  const stateInfo = getStateLabel(agentState);

  return (
    <div
      className={cn(
        chatOpen
          ? 'relative z-40 flex w-full shrink-0 items-center justify-center border-b border-zinc-800/80 bg-zinc-950/90 pt-16 pb-4'
          : 'absolute inset-x-0 top-8 bottom-32 z-50 md:top-12 md:bottom-40'
      )}
    >
      <div
        className={cn(
          chatOpen
            ? 'flex w-full max-w-2xl items-center justify-start px-4 md:px-6'
            : 'relative mx-auto h-full max-w-2xl px-4 md:px-0'
        )}
      >
        {chatOpen ? (
          /* Render compact agent container directly, bypassing grid */
          <motion.div
            key="agent-container"
            layoutId="agent-container"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{
              ...ANIMATION_TRANSITION,
              delay: animationDelay,
            }}
            className="flex w-full flex-row items-center justify-start gap-6 pl-6 md:pl-12"
          >
            {/* Visualizer Block */}
            <div className="relative aspect-square h-[90px] w-[90px] shrink-0">
              {lowBandwidthMode ? (
                <motion.div
                  key="low-bandwidth-visualizer"
                  initial={{ scale: 1 }}
                  animate={{ scale: 0.25 }}
                  transition={{
                    ...ANIMATION_TRANSITION,
                    delay: animationDelay,
                  }}
                  className="absolute top-1/2 left-1/2 flex size-[180px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-zinc-800 bg-zinc-950/80 shadow-2xl transition-all"
                >
                  <div
                    className={cn(
                      'border-primary rounded-full border-4 border-dashed transition-all duration-1000 ease-in-out',
                      agentState === 'speaking' ||
                        agentState === 'listening' ||
                        agentState === 'thinking'
                        ? 'scale-100 animate-pulse opacity-100'
                        : 'scale-95 opacity-30',
                      'size-[120px]'
                    )}
                  />
                </motion.div>
              ) : (
                <AudioVisualizer
                  key="audio-visualizer"
                  initial={{ scale: 1 }}
                  animate={{ scale: 0.2 }}
                  transition={{
                    ...ANIMATION_TRANSITION,
                    delay: animationDelay,
                  }}
                  audioVisualizerType={audioVisualizerType}
                  audioVisualizerColor={audioVisualizerColor}
                  audioVisualizerColorShift={audioVisualizerColorShift}
                  audioVisualizerBarCount={audioVisualizerBarCount}
                  audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
                  audioVisualizerRadialRadius={audioVisualizerRadialRadius}
                  audioVisualizerGridRowCount={audioVisualizerGridRowCount}
                  audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
                  audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
                  isChatOpen={chatOpen}
                  className="bg-background border-input absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-[50px] border shadow-2xl/10 transition-[border,drop-shadow] delay-200"
                  style={{ color: audioVisualizerColor }}
                />
              )}
            </div>

            {/* Bilingual Status Label */}
            <div className="flex flex-col items-start text-left font-sans transition-all duration-300">
              <div className="flex items-center gap-2">
                <span className={cn('h-2.5 w-2.5 shrink-0 rounded-full', stateInfo.dotColor)} />
                <span
                  className={cn(
                    'font-sans text-sm leading-none font-black tracking-wider uppercase md:text-base',
                    stateInfo.colorClass
                  )}
                >
                  {stateInfo.en}
                </span>
              </div>
              <span className="text-muted-foreground mt-0.5 font-sans text-xs leading-normal font-bold">
                {stateInfo.hi}
              </span>
            </div>
          </motion.div>
        ) : (
          /* Normal grid layout when chat is closed */
          <div className={cn(tileViewClassNames.grid)}>
            {/* Agent */}
            <div className={cn(['grid', tileViewClassNames.agentChatClosed])}>
              <AnimatePresence mode="popLayout">
                {!isAvatar && (
                  // Audio Agent
                  <motion.div
                    key="agent-container"
                    layoutId="agent-container"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{
                      ...ANIMATION_TRANSITION,
                      delay: animationDelay,
                    }}
                    className="relative flex h-full w-full flex-col items-center justify-center gap-8"
                  >
                    {/* Visualizer Block */}
                    <div className="relative aspect-square h-[90px] w-[90px] shrink-0">
                      {lowBandwidthMode ? (
                        <motion.div
                          key="low-bandwidth-visualizer"
                          initial={{ scale: 1 }}
                          animate={{ scale: 1 }}
                          transition={{
                            ...ANIMATION_TRANSITION,
                            delay: animationDelay,
                          }}
                          className="absolute top-1/2 left-1/2 flex size-[260px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-zinc-800 bg-zinc-950/80 shadow-2xl transition-all"
                        >
                          <div
                            className={cn(
                              'border-primary rounded-full border-4 border-dashed transition-all duration-1000 ease-in-out',
                              agentState === 'speaking' ||
                                agentState === 'listening' ||
                                agentState === 'thinking'
                                ? 'scale-100 animate-pulse opacity-100'
                                : 'scale-95 opacity-30',
                              'size-[180px]'
                            )}
                          />
                        </motion.div>
                      ) : (
                        <AudioVisualizer
                          key="audio-visualizer"
                          initial={{ scale: 1 }}
                          animate={{ scale: 1 }}
                          transition={{
                            ...ANIMATION_TRANSITION,
                            delay: animationDelay,
                          }}
                          audioVisualizerType={audioVisualizerType}
                          audioVisualizerColor={audioVisualizerColor}
                          audioVisualizerColorShift={audioVisualizerColorShift}
                          audioVisualizerBarCount={audioVisualizerBarCount}
                          audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
                          audioVisualizerRadialRadius={audioVisualizerRadialRadius}
                          audioVisualizerGridRowCount={audioVisualizerGridRowCount}
                          audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
                          audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
                          isChatOpen={chatOpen}
                          className="bg-background absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-[50px] border border-transparent transition-[border,drop-shadow]"
                          style={{ color: audioVisualizerColor }}
                        />
                      )}
                    </div>

                    {/* Bilingual Status Label */}
                    <div className="absolute top-1/2 left-1/2 flex w-full -translate-x-1/2 translate-y-[160px] flex-col items-center text-center font-sans transition-all duration-300 md:translate-y-[180px]">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn('h-2.5 w-2.5 shrink-0 rounded-full', stateInfo.dotColor)}
                        />
                        <span
                          className={cn(
                            'font-sans leading-none font-black tracking-wider uppercase',
                            'text-3xl md:text-5xl',
                            stateInfo.colorClass
                          )}
                        >
                          {stateInfo.en}
                        </span>
                      </div>
                      <span
                        className={cn(
                          'text-muted-foreground font-sans leading-normal font-bold',
                          'mt-1.5 text-base md:text-xl'
                        )}
                      >
                        {stateInfo.hi}
                      </span>
                    </div>
                  </motion.div>
                )}

                {isAvatar && (
                  // Avatar Agent
                  <motion.div
                    key="avatar"
                    layoutId="avatar"
                    initial={{
                      scale: 1,
                      opacity: 1,
                      maskImage:
                        'radial-gradient(circle, rgba(0, 0, 0, 1) 0, rgba(0, 0, 0, 1) 20px, transparent 20px)',
                      filter: 'blur(20px)',
                    }}
                    animate={{
                      maskImage:
                        'radial-gradient(circle, rgba(0, 0, 0, 1) 0, rgba(0, 0, 0, 1) 500px, transparent 500px)',
                      filter: 'blur(0px)',
                      borderRadius: chatOpen ? 6 : 12,
                    }}
                    transition={{
                      ...ANIMATION_TRANSITION,
                      delay: animationDelay,
                      maskImage: {
                        duration: 1,
                      },
                      filter: {
                        duration: 1,
                      },
                    }}
                    className={cn(
                      'overflow-hidden bg-black drop-shadow-xl/80',
                      chatOpen ? 'h-[90px]' : 'h-auto w-full'
                    )}
                  >
                    <VideoTrack
                      width={videoWidth}
                      height={videoHeight}
                      trackRef={agentVideoTrack}
                      className={cn(chatOpen && 'size-[90px] object-cover')}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div
              className={cn([
                'grid',
                chatOpen && tileViewClassNames.secondTileChatOpen,
                !chatOpen && tileViewClassNames.secondTileChatClosed,
              ])}
            >
              {/* Camera & Screen Share */}
              <AnimatePresence>
                {((cameraTrack && isCameraEnabled) ||
                  (screenShareTrack && isScreenShareEnabled)) && (
                  <motion.div
                    key="camera"
                    layout="position"
                    layoutId="camera"
                    initial={{
                      opacity: 0,
                      scale: 0,
                    }}
                    animate={{
                      opacity: 1,
                      scale: 1,
                    }}
                    exit={{
                      opacity: 0,
                      scale: 0,
                    }}
                    transition={{
                      ...ANIMATION_TRANSITION,
                      delay: animationDelay,
                    }}
                    className="aspect-square size-[90px] drop-shadow-lg/20"
                  >
                    <VideoTrack
                      trackRef={cameraTrack || screenShareTrack}
                      width={(cameraTrack || screenShareTrack)?.publication.dimensions?.width ?? 0}
                      height={
                        (cameraTrack || screenShareTrack)?.publication.dimensions?.height ?? 0
                      }
                      className="bg-muted aspect-square size-[90px] rounded-md object-cover"
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
