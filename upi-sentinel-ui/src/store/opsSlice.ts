import { createSlice, configureStore, type PayloadAction } from '@reduxjs/toolkit';

interface OpsState {
    activeTxnId: string | null;
    userRole: 'l1_support' | 'ops_lead';
}

const initialState: OpsState = {
    activeTxnId: null,
    userRole: 'l1_support'
}

const opsSlice = createSlice({
    name: 'ops',
    initialState,
    reducers: {
        setActiveTxn: (state, action: PayloadAction<string>) => {
            state.activeTxnId = action.payload;
        },
        setUserRole: (state, action: PayloadAction<'l1_support' | 'ops_lead'>) => {
            state.userRole = action.payload;
        },
    },
});

export const {setActiveTxn, setUserRole} = opsSlice.actions;

export const store = configureStore({
  reducer: {
    ops: opsSlice.reducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;