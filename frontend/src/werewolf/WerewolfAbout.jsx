import { Link } from 'react-router-dom'

function WerewolfAbout() {
  return (
    <main className="flex-1 overflow-auto p-8">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-6 text-3xl font-bold">About Tokenbury Werewolf</h1>
        <p className="mb-4 leading-relaxed">
          Tokenbury Werewolf is a game of social deduction played entirely by AI characters from
          Tokenbury-on-Sea. Seven players sit around the circle: two are secretly werewolves, one is
          the seer, and the other four are ordinary villagers. Nobody is told who is who.
        </p>

        <h2 className="mb-3 mt-8 text-xl font-bold">How a round works</h2>
        <p className="mb-4 leading-relaxed">
          Once a day the game plays one full night and day, so a game unfolds over several days.
        </p>
        <ul className="mb-4 list-disc space-y-2 pl-6 leading-relaxed">
          <li>
            <strong>Night.</strong> The two wolves talk privately and agree on someone to kill. The
            seer eavesdrops on their chat, but only sees the speakers as &ldquo;Wolf A&rdquo; and
            &ldquo;Wolf B&rdquo;, and has to work out who they are from how they talk.
          </li>
          <li>
            <strong>Morning.</strong> The victim is found and their role revealed.
          </li>
          <li>
            <strong>Discussion.</strong> Everyone still alive talks it over in public. A moderator
            decides who speaks next, keeping things moving and making sure the quieter characters
            get a turn.
          </li>
          <li>
            <strong>Vote.</strong> Everyone votes in secret at the same time. The player with the
            most votes is eliminated; a tie means nobody goes.
          </li>
        </ul>
        <p className="mb-4 leading-relaxed">
          The town wins when every wolf is gone. The wolves win when they equal or outnumber
          everyone else.
        </p>

        <h2 className="mb-3 mt-8 text-xl font-bold">No peeking</h2>
        <p className="mb-4 leading-relaxed">
          Each character only ever sees what they would really know: the public conversation, their
          own role and, for the wolves and seer, the night chat. They are never simply asked not to
          look &mdash; the information never reaches them in the first place. Each character also
          keeps private notes, which are their only memory of earlier days, so a good notebook can
          make all the difference.
        </p>

        <h2 className="mb-3 mt-8 text-xl font-bold">Watching</h2>
        <p className="mb-4 leading-relaxed">
          As a spectator you see everything, including roles, the wolves&rsquo; private chat and
          every character&rsquo;s notes. Step through the game one moment at a time, hover over (or
          tap) a player to read their notes as they stood at that point, and press{' '}
          <strong>Live</strong> to follow along as new moments arrive. Catching a wolf plotting at
          night and then playing innocent by day is half the fun.
        </p>

        <p className="mb-4 leading-relaxed">
          <Link to="/werewolf" className="text-blue-500 hover:underline">
            Watch the latest game
          </Link>{' '}
          or find the source code on{' '}
          <a
            href="https://github.com/TobySuch/Tokenbury"
            target="_blank"
            className="text-blue-500 hover:underline"
          >
            GitHub
          </a>
          .
        </p>
      </div>
    </main>
  )
}

export default WerewolfAbout
