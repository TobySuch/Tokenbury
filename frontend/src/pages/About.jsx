function About() {
  return (
    <main className="flex-1 overflow-auto p-8">
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-6 text-3xl font-bold">About Tokenbury-on-Sea</h1>
        <p className="mb-4 leading-relaxed">
          Tokenbury-on-Sea is a living, watchable AI simulation of a sleepy English coastal town.
          Originally inspired by the paper{' '}
          <a
            href="https://arxiv.org/abs/2304.03442"
            target="_blank"
            className="text-blue-500 hover:underline"
          >
            Generative Agents: Interactive Simulacra of Human Behavior
          </a>
          , the project is a sandbox for exploring how large language models can be used to create
          dynamic, interactive narratives. The town is populated by a cast of characters, each with
          their own personalities, goals, and relationships.
        </p>
        <p className="mb-4 leading-relaxed">
          Currently the agents make a plan at the start of each day, and then generate a 'tick'
          every 30 minutes, calculating their location for the next half hour, along with actions,
          inner thoughts and moods. They are aware of their surroundings, and who is around them. In
          the future they will have memories, and be able to interact with each other and their
          environment in more complex ways.
        </p>
        <p className="mb-4 leading-relaxed">
          This project is a work in progress. Check in often to see how the agents and the town
          evolve!
        </p>

        <p className="mb-4 leading-relaxed">
          You can find the source code on{' '}
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

export default About
