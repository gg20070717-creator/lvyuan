/**
 * 安全的 localStorage 封装
 * 在沙箱环境（如 IdeaLab 静态页面）中自动降级到内存存储
 */

// 检测 localStorage 是否可用
function isLocalStorageAvailable(): boolean {
  try {
    const testKey = '__storage_test__'
    localStorage.setItem(testKey, 'test')
    localStorage.removeItem(testKey)
    return true
  } catch {
    return false
  }
}

// 内存存储（降级方案）
const memoryStore = new Map<string, string>()

// 安全存储对象
const safeStorage: Storage = {
  get length() {
    return isLocalStorageAvailable() ? localStorage.length : memoryStore.size
  },
  
  clear() {
    if (isLocalStorageAvailable()) {
      localStorage.clear()
    } else {
      memoryStore.clear()
    }
  },
  
  getItem(key: string) {
    if (isLocalStorageAvailable()) {
      return localStorage.getItem(key)
    }
    return memoryStore.get(key) ?? null
  },
  
  key(index: number) {
    if (isLocalStorageAvailable()) {
      return localStorage.key(index)
    }
    const keys = Array.from(memoryStore.keys())
    return keys[index] ?? null
  },
  
  removeItem(key: string) {
    if (isLocalStorageAvailable()) {
      localStorage.removeItem(key)
    } else {
      memoryStore.delete(key)
    }
  },
  
  setItem(key: string, value: string) {
    if (isLocalStorageAvailable()) {
      localStorage.setItem(key, value)
    } else {
      memoryStore.set(key, value)
    }
  }
}

export default safeStorage
