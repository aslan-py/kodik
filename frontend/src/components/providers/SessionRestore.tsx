'use client';

import { useEffect } from 'react';
import { useAppDispatch } from '@/hooks/storeHooks';
import { checkUserAuth } from '@/store/authSlice';

export function SessionRestore() {
  const dispatch = useAppDispatch();

  useEffect(() => {
    dispatch(checkUserAuth());
  }, [dispatch]);

  return null;
}