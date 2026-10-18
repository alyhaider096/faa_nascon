import { Redirect, useLocalSearchParams } from 'expo-router';
import React from 'react';
import { Platform } from 'react-native';
export default function StreamDeepLink() { const { id } = useLocalSearchParams<{ id: string }>(); return <Redirect href={Platform.OS === 'web' ? `/web/costream/${id}` : `/costream/${id}`} />; }

