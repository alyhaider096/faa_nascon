import { useLocalSearchParams } from 'expo-router';
import React from 'react';
import { GuestExperience } from '../../../../components/GuestExperience';
export default function GuestMatchNotice() { const { id, state } = useLocalSearchParams<{ id: string; state?: string }>(); return <GuestExperience id={id} mode="notice" noticeState={state} />; }

