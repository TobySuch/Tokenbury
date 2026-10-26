import { Link } from 'react-router-dom'
import usePageTitle from '../hooks/usePageTitle'

function NotFound() {
  usePageTitle('Page not found · Tokenbury-on-Sea')
  return (
    <main className="flex-1 overflow-auto p-8">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-6 text-3xl font-bold">Page not found</h1>
        <p className="mb-4 leading-relaxed">
          Nobody in Tokenbury-on-Sea has heard of this page. Perhaps it washed out with the tide.
        </p>
        <p className="mb-4 leading-relaxed">
          <Link to="/" className="text-blue-500 hover:underline">
            Back to the town
          </Link>
        </p>
      </div>
    </main>
  )
}

export default NotFound
