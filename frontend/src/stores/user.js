import { defineStore } from 'pinia'
import http from '@/api'

export const useUserStore = defineStore('user', {
  state: () => ({
    active: null,
    list: []
  }),
  actions: {
    async fetchActive() {
      this.active = await http.get('/users/active')
      return this.active
    },
    async fetchList() {
      this.list = await http.get('/users')
      return this.list
    },
    async activate(id) {
      this.active = await http.post(`/users/${id}/activate`)
      await this.fetchList()
      return this.active
    },
    async remove(id) {
      await http.delete(`/users/${id}`)
      await this.fetchList()
      try {
        await this.fetchActive()
      } catch (e) {
        this.active = null
      }
    }
  }
})