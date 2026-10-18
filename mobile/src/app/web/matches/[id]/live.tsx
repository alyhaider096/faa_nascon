import { useLocalSearchParams } from 'expo-router';
import React from 'react';
import { GuestExperience } from '../../../../components/GuestExperience';
export default function GuestLiveMatch() { const { id } = useLocalSearchParams<{ id: string }>(); return <GuestExperience id={id} mode="live" />; }

