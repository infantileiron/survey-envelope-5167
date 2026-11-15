import {request} from './client';import type {Reconciliation,ReconciliationDetail} from '../types/domain';export const list=()=>request<Reconciliation[]>('/reconciliations');
export const create=(data:unknown)=>request<Reconciliation>('/reconciliations',data);
export const detail=(id:string)=>request<ReconciliationDetail>('/reconciliations/'+id);
