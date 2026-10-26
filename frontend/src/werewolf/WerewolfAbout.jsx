import { Link } from 'react-router-dom'
import usePageTitle from '../hooks/usePageTitle'

function WerewolfAbout() {
  usePageTitle('About · Tokenbury Werewolf')
  return (
    <main className="flex-1 overflow-auto p-8">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-6 text-3xl font-bold">About Tokenbury Werewolf</h1>
        <p className="mb-4 leading-relaxed">
          Tokenbury Werewolf is a game of social deduction played entirely by AI characters from
          Tokenbury-on-Sea. Each game seats between five and twelve players around the circle. One
          or more are secretly werewolves; the rest are townsfolk, among them a seer, usually a
          doctor, and ordinary villagers. Everyone is told how many of each role are in the game,
          but nobody is told who is who.
        </p>

        <h2 className="mb-3 mt-8 text-xl font-bold">The roles</h2>
        <ul className="mb-4 list-disc space-y-2 pl-6 leading-relaxed">
          <li>
            <strong>Werewolves</strong> know each other and pick someone to kill each night. In
            their private chat they appear only as &ldquo;Wolf A&rdquo;, &ldquo;Wolf B&rdquo; and so
            on.
          </li>
          <li>
            <strong>The seer</strong> eavesdrops on the wolves&rsquo; night chat, but only sees
            those labels, never names, and has to work out who is talking from how they talk.
          </li>
          <li>
            <strong>The doctor</strong> protects one player each night, possibly themselves, but
            never the same person two nights running. If the wolves pick the protected player,
            nobody dies.
          </li>
          <li>
            <strong>Villagers</strong> have no special powers, just their wits and their votes.
          </li>
        </ul>

        <h2 className="mb-3 mt-8 text-xl font-bold">The lovers</h2>
        <p className="mb-4 leading-relaxed">
          In most games two players are secretly linked as lovers. They know who their partner is
          (though not their partner&rsquo;s role) and get a few private words each night. If one of
          them dies, the other dies of a broken heart. A wolf can fall for a villager, and if the
          two of them are the last left alive, the lovers win together.
        </p>

        <h2 className="mb-3 mt-8 text-xl font-bold">How a round works</h2>
        <p className="mb-4 leading-relaxed">
          Once a day the game plays one full night and day, so a game unfolds over several days.
        </p>
        <ul className="mb-4 list-disc space-y-2 pl-6 leading-relaxed">
          <li>
            <strong>Night.</strong> The wolves agree on a victim while the seer listens in. The
            doctor makes their rounds, and the lovers whisper to each other.
          </li>
          <li>
            <strong>Morning.</strong> The victim is found and their role revealed, unless the doctor
            got there first, in which case nobody died.
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
          everyone else. A game that runs out of days ends in a draw.
        </p>

        <h2 className="mb-3 mt-8 text-xl font-bold">No peeking</h2>
        <p className="mb-4 leading-relaxed">
          Each character only ever sees what they would really know: the public conversation, their
          own role and, depending on their role, the wolves&rsquo; night chat or the lovers&rsquo;
          whispers. They are never simply asked not to look &mdash; the information never reaches
          them in the first place. Each character also keeps private notes, which are their only
          memory of earlier days, so a good notebook can make all the difference.
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
