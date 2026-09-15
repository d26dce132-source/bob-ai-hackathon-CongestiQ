import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Overview  from './pages/Overview'
import Vessels   from './pages/Vessels'
import Congestion from './pages/Congestion'
import Resources from './pages/Resources'
import Routing   from './pages/Routing'
import Plan      from './pages/Plan'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"           element={<Overview />} />
        <Route path="/vessels"    element={<Vessels />} />
        <Route path="/congestion" element={<Congestion />} />
        <Route path="/resources"  element={<Resources />} />
        <Route path="/routing"    element={<Routing />} />
        <Route path="/plan"       element={<Plan />} />
      </Routes>
    </BrowserRouter>
  )
}
